import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const UI_ROOT = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_ROOT = path.resolve(UI_ROOT, "../results");
const SUITE_CONTAINERS = ["suite", "suites"];

async function readJson(filePath, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return fallback;
    throw error;
  }
}

async function listDirectories(directory) {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}

function resultKey(directory) {
  return path.relative(RESULTS_ROOT, directory).split(path.sep).join("/");
}

async function summarizeRun(directory, metadata = {}) {
  const manifest = await readJson(path.join(directory, "manifest.json"));
  const metrics = await readJson(path.join(directory, "metrics.json"));
  if (!manifest || !metrics) return null;

  const key = resultKey(directory);
  const models = Array.isArray(manifest.models)
    ? manifest.models
    : Object.keys(metrics);

  return {
    key,
    runId: manifest.run_id ?? path.basename(directory),
    createdAt: manifest.created_at ?? null,
    kind: manifest.kind ?? metadata.kind ?? "quality",
    dataset: manifest.dataset ?? manifest.dataset_id ?? null,
    cases: manifest.cases ?? null,
    models,
    source: metadata.source ?? "run",
    suiteId: metadata.suiteId ?? null,
    pairedLatencyKey: metadata.pairedLatencyKey ?? null,
  };
}

async function discoverRuns() {
  const runs = [];
  const rootDirectories = await listDirectories(RESULTS_ROOT);

  for (const name of rootDirectories) {
    if (SUITE_CONTAINERS.includes(name)) continue;
    const run = await summarizeRun(path.join(RESULTS_ROOT, name), { source: "run" });
    if (run) runs.push(run);
  }

  for (const containerName of SUITE_CONTAINERS) {
    const container = path.join(RESULTS_ROOT, containerName);
    const suiteIds = await listDirectories(container);

    for (const suiteId of suiteIds) {
      const suiteRoot = path.join(container, suiteId);
      const qualityDir = path.join(suiteRoot, "quality");
      const latencyDir = path.join(suiteRoot, "latency");

      const latency = await summarizeRun(latencyDir, {
        kind: "latency",
        source: "suite-latency",
        suiteId,
      });

      const quality = await summarizeRun(qualityDir, {
        kind: "quality",
        source: "suite",
        suiteId,
        pairedLatencyKey: latency?.key ?? null,
      });

      if (quality) runs.push(quality);
      else if (latency) runs.push(latency);
    }
  }

  return runs.sort((left, right) => {
    const leftTime = Date.parse(left.createdAt ?? "") || 0;
    const rightTime = Date.parse(right.createdAt ?? "") || 0;
    if (leftTime !== rightTime) return rightTime - leftTime;
    return right.key.localeCompare(left.key);
  });
}

async function loadRun(key) {
  const runs = await discoverRuns();
  const summary = runs.find((item) => item.key === key);
  if (!summary) return null;

  const directory = path.resolve(RESULTS_ROOT, ...key.split("/"));
  const metrics = await readJson(path.join(directory, "metrics.json"), {});
  const manifest = await readJson(path.join(directory, "manifest.json"), {});
  const failures = await readJson(path.join(directory, "failures.json"), {});

  let latency = null;
  if (summary.pairedLatencyKey) {
    const latencyDirectory = path.resolve(
      RESULTS_ROOT,
      ...summary.pairedLatencyKey.split("/"),
    );
    latency = {
      key: summary.pairedLatencyKey,
      manifest: await readJson(path.join(latencyDirectory, "manifest.json"), {}),
      metrics: await readJson(path.join(latencyDirectory, "metrics.json"), {}),
    };
  }

  return { summary, manifest, metrics, failures, latency };
}

function sendJson(response, status, payload) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(payload));
}

function resultsApi() {
  const middleware = async (request, response, next) => {
    try {
      const url = new URL(request.url, "http://localhost");

      if (url.pathname === "/api/runs") {
        sendJson(response, 200, { runs: await discoverRuns() });
        return;
      }

      if (url.pathname === "/api/run") {
        const key = url.searchParams.get("key");
        if (!key) {
          sendJson(response, 400, { error: "Missing run key" });
          return;
        }
        const run = await loadRun(key);
        if (!run) {
          sendJson(response, 404, { error: "Run not found" });
          return;
        }
        sendJson(response, 200, run);
        return;
      }

      next();
    } catch (error) {
      sendJson(response, 500, {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  };

  return {
    name: "redact-bench-results-api",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}

export default defineConfig({
  plugins: [react(), resultsApi()],
});
