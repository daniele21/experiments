import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_ROOT = path.resolve(
  process.env.IMAGEGEN_RESULTS_ROOT || path.join(HERE, "..", "results"),
);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') quoted = true;
    else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else field += char;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) return [];
  const [header, ...body] = rows;
  return body
    .filter((values) => values.some((value) => value !== ""))
    .map((values) =>
      Object.fromEntries(header.map((key, index) => [key, values[index] ?? ""])),
    );
}

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return fallback;
    throw error;
  }
}

function safeRunDir(runId) {
  if (!/^[A-Za-z0-9._-]+$/.test(runId || "")) {
    throw new Error("invalid run id");
  }
  return path.join(RESULTS_ROOT, runId);
}

function safeArtifact(runId, relativePath) {
  const root = safeRunDir(runId);
  const resolved = path.resolve(root, relativePath || "");
  if (resolved !== root && !resolved.startsWith(root + path.sep)) {
    throw new Error("artifact path escapes run directory");
  }
  return resolved;
}

function parseObject(raw) {
  try {
    const value = JSON.parse(raw || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function rowView(runId, row) {
  const metadata = parseObject(row.provider_metadata);
  return {
    ...row,
    valid: String(row.valid).toLowerCase() === "true",
    latency_ms: Number(row.latency_ms || 0),
    generation_config: parseObject(row.generation_config),
    provider_metadata: metadata,
    artifact_url: row.artifact_path
      ? `/api/artifact?run=${encodeURIComponent(runId)}&path=${encodeURIComponent(row.artifact_path)}`
      : null,
  };
}

async function loadRun(runId) {
  const dir = safeRunDir(runId);
  const [manifest, csv] = await Promise.all([
    readJson(path.join(dir, "manifest.json"), {}),
    fs.readFile(path.join(dir, "evidence.csv"), "utf8"),
  ]);
  const rows = parseCsv(csv).map((row) => rowView(runId, row));
  return { runId, manifest, rows };
}

async function discoverRuns() {
  let entries = [];
  try {
    entries = await fs.readdir(RESULTS_ROOT, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  const runs = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    try {
      const { manifest, rows } = await loadRun(entry.name);
      const models = [...new Set(rows.map((row) => row.model_key))];
      const categories = [...new Set(rows.map((row) => row.category))];
      runs.push({
        runId: entry.name,
        createdAt: manifest.created_at_utc ?? null,
        suite: manifest.suite ?? null,
        profile: manifest.parameters?.profile ?? null,
        models,
        categories,
        prompts: new Set(rows.map((row) => row.prompt_id)).size,
        valid: rows.filter((row) => row.valid).length,
        total: rows.length,
      });
    } catch {
      // Ignore incomplete directories until evidence + manifest exist.
    }
  }
  return runs.sort((a, b) =>
    String(b.createdAt || b.runId).localeCompare(String(a.createdAt || a.runId)),
  );
}

function blindPair(promptId, firstModel, secondModel, seed) {
  const digest = crypto
    .createHash("sha256")
    .update(`${seed}:${promptId}:${firstModel}:${secondModel}`)
    .digest("hex");
  const swap = Number.parseInt(digest.at(-1), 16) % 2 === 1;
  return {
    pair_id: `pair-${digest.slice(0, 16)}`,
    prompt_id: promptId,
    model_for_a: swap ? secondModel : firstModel,
    model_for_b: swap ? firstModel : secondModel,
  };
}

function combinations(values) {
  const pairs = [];
  for (let left = 0; left < values.length; left += 1) {
    for (let right = left + 1; right < values.length; right += 1) {
      pairs.push([values[left], values[right]]);
    }
  }
  return pairs;
}

async function blindView(runId, reveal = false) {
  const run = await loadRun(runId);
  const requested = run.manifest.requested_models?.model_keys ?? [];
  const seed = Number(run.manifest.parameters?.seed ?? 0);
  const byPrompt = new Map();
  for (const row of run.rows) {
    if (!row.artifact_url) continue;
    if (!byPrompt.has(row.prompt_id)) byPrompt.set(row.prompt_id, new Map());
    byPrompt.get(row.prompt_id).set(row.model_key, row);
  }
  const pairs = [];
  for (const [promptId, modelRows] of byPrompt.entries()) {
    const available = requested.filter((model) => modelRows.has(model)).sort();
    for (const [first, second] of combinations(available)) {
      const pair = blindPair(promptId, first, second, seed);
      const rowA = modelRows.get(pair.model_for_a);
      const rowB = modelRows.get(pair.model_for_b);
      pairs.push({
        pair_id: pair.pair_id,
        prompt_id: promptId,
        category: rowA.category,
        prompt: rowA.prompt,
        image_a: rowA.artifact_url,
        image_b: rowB.artifact_url,
        ...(reveal
          ? { model_for_a: pair.model_for_a, model_for_b: pair.model_for_b }
          : {}),
      });
    }
  }
  return { runId, pairs };
}

function sendJson(response, status, payload) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(payload));
}

function resultsApi() {
  return {
    name: "imagegen-results-api",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        try {
          const url = new URL(request.url, "http://localhost");
          if (url.pathname === "/api/runs") {
            sendJson(response, 200, { runs: await discoverRuns() });
            return;
          }
          if (url.pathname === "/api/run") {
            const run = url.searchParams.get("run");
            sendJson(response, 200, await loadRun(run));
            return;
          }
          if (url.pathname === "/api/blind") {
            const run = url.searchParams.get("run");
            sendJson(response, 200, await blindView(run, false));
            return;
          }
          if (url.pathname === "/api/blind-key") {
            const run = url.searchParams.get("run");
            sendJson(response, 200, await blindView(run, true));
            return;
          }
          if (url.pathname === "/api/artifact") {
            const run = url.searchParams.get("run");
            const artifact = safeArtifact(run, url.searchParams.get("path"));
            const bytes = await fs.readFile(artifact);
            const ext = path.extname(artifact).toLowerCase();
            const mime = {
              ".png": "image/png",
              ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg",
              ".webp": "image/webp",
            }[ext] || "application/octet-stream";
            response.statusCode = 200;
            response.setHeader("Content-Type", mime);
            response.setHeader("Cache-Control", "no-store");
            response.end(bytes);
            return;
          }
          next();
        } catch (error) {
          sendJson(response, 400, {
            error: error instanceof Error ? error.message : String(error),
          });
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), resultsApi()],
  server: { host: "127.0.0.1", port: 5173 },
});
