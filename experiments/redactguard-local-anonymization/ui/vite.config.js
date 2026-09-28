import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const UI_ROOT = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_ROOT = path.resolve(UI_ROOT, "../results");
const SUITE_CONTAINERS = ["suite", "suites"];
const RESERVED_JSONL = new Set(["history.jsonl"]);

async function readJson(filePath, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return fallback;
    throw error;
  }
}

async function readJsonLines(filePath) {
  try {
    const body = await fs.readFile(filePath, "utf8");
    const rows = [];
    for (const line of body.split("\n")) {
      if (!line.trim()) continue;
      try {
        rows.push(JSON.parse(line));
      } catch {
        // A process interrupted mid-write can leave one truncated trailing line.
        // Preserve all complete JSONL evidence written before it.
      }
    }
    return rows;
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}

async function listEntries(directory) {
  try {
    return await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}

async function listDirectories(directory) {
  const entries = await listEntries(directory);
  return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
}

async function listModelJsonlFiles(directory) {
  const entries = await listEntries(directory);
  return entries
    .filter(
      (entry) =>
        entry.isFile() &&
        entry.name.endsWith(".jsonl") &&
        !RESERVED_JSONL.has(entry.name),
    )
    .map((entry) => entry.name);
}

function resultKey(directory) {
  return path.relative(RESULTS_ROOT, directory).split(path.sep).join("/");
}

function parseRunDate(name) {
  const match = name.match(/^(\d{8})T(\d{6})Z/);
  if (!match) return null;
  const [, day, clock] = match;
  const iso =
    `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}T` +
    `${clock.slice(0, 2)}:${clock.slice(2, 4)}:${clock.slice(4, 6)}Z`;
  return Number.isNaN(Date.parse(iso)) ? null : iso;
}

function ratio(numerator, denominator, empty = 0) {
  return denominator ? numerator / denominator : empty;
}

function percentile(values, q) {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const index = (ordered.length - 1) * q;
  const low = Math.floor(index);
  const high = Math.min(low + 1, ordered.length - 1);
  const fraction = index - low;
  return ordered[low] * (1 - fraction) + ordered[high] * fraction;
}

function aggregatePartial(rows) {
  if (!rows.length) return null;

  const validRows = rows.filter((row) => row.valid);
  const sum = (key) => rows.reduce((total, row) => total + Number(row[key] ?? 0), 0);
  const tp = sum("tp");
  const fp = sum("fp");
  const fn = sum("fn");
  const exactTp = sum("exact_tp");
  const goldCount = sum("gold_count");
  const predictedCount = sum("predicted_count");
  const goldChars = sum("gold_chars");
  const leakedChars = sum("leaked_chars");
  const overredactedChars = sum("overredacted_chars");
  const nonPiiChars = sum("non_pii_chars");
  const latencies = validRows
    .map((row) => Number(row.latency_ms))
    .filter((value) => Number.isFinite(value));
  const recall = ratio(tp, tp + fn, 1);
  const precision = ratio(tp, tp + fp, 1);
  const spanF1 = precision + recall ? (2 * precision * recall) / (precision + recall) : 0;

  const byTypeCounters = new Map();
  for (const row of rows) {
    for (const [piiType, values] of Object.entries(row.by_type ?? {})) {
      const current = byTypeCounters.get(piiType) ?? {
        gold_count: 0,
        predicted_count: 0,
        tp: 0,
        exact_tp: 0,
        overlap_tp: 0,
        fp: 0,
        fn: 0,
        gold_chars: 0,
        leaked_chars: 0,
      };
      for (const key of Object.keys(current)) {
        current[key] += Number(values[key] ?? 0);
      }
      byTypeCounters.set(piiType, current);
    }
  }

  const byType = {};
  for (const [piiType, counts] of [...byTypeCounters.entries()].sort()) {
    const typeRecall = ratio(counts.tp, counts.tp + counts.fn, 1);
    const typePrecision = ratio(counts.tp, counts.tp + counts.fp, 1);
    byType[piiType] = {
      ...counts,
      pii_recall: typeRecall,
      precision: typePrecision,
      span_f1:
        typePrecision + typeRecall
          ? (2 * typePrecision * typeRecall) / (typePrecision + typeRecall)
          : 0,
      exact_match_recall: ratio(counts.exact_tp, counts.gold_count, 1),
      leakage_rate: ratio(counts.leaked_chars, counts.gold_chars),
    };
  }

  const failures = rows
    .filter(
      (row) =>
        Number(row.fn ?? 0) ||
        Number(row.fp ?? 0) ||
        Number(row.leaked_chars ?? 0) ||
        Number(row.overredacted_chars ?? 0) ||
        row.error,
    )
    .map((row) => ({
      case_id: row.case_id,
      profile: row.profile,
      pii_recall: row.pii_recall,
      precision: row.precision,
      leakage_rate: row.leakage_rate,
      over_redaction_rate: row.over_redaction_rate,
      fn: row.fn,
      fp: row.fp,
      failures: row.valid ? 0 : 1,
      false_negatives: row.false_negatives ?? [],
      false_positives: row.false_positives ?? [],
      error: row.error ?? null,
    }))
    .sort(
      (left, right) =>
        Number(right.leakage_rate ?? 0) - Number(left.leakage_rate ?? 0) ||
        Number(right.fn ?? 0) - Number(left.fn ?? 0) ||
        Number(right.fp ?? 0) - Number(left.fp ?? 0),
    );

  const micro = {
    cases: rows.length,
    valid_output_rate: ratio(validRows.length, rows.length),
    gold_count: goldCount,
    predicted_count: predictedCount,
    tp,
    exact_tp: exactTp,
    fp,
    fn,
    pii_recall: recall,
    precision,
    span_f1: spanF1,
    exact_match_recall: ratio(exactTp, goldCount, 1),
    leakage_rate: ratio(leakedChars, goldChars),
    zero_leak_document_rate: ratio(
      rows.filter((row) => Boolean(row.zero_leak)).length,
      rows.length,
    ),
    over_redaction_rate: ratio(overredactedChars, nonPiiChars),
    leaked_chars: leakedChars,
    gold_chars: goldChars,
    overredacted_chars: overredactedChars,
    non_pii_chars: nonPiiChars,
    latency_p50_ms: percentile(latencies, 0.5),
    latency_p95_ms: percentile(latencies, 0.95),
    latency_p99_ms: percentile(latencies, 0.99),
    failures: rows.length - validRows.length,
  };

  return {
    ...micro,
    evaluation_schema: "redactguard-evaluation-v2-partial",
    micro,
    macro: {},
    by_type: byType,
    by_profile: {},
    by_document: {},
    dataset_balance: {},
    failure_analysis: failures,
  };
}

async function readPartialEvidence(directory) {
  const files = await listModelJsonlFiles(directory);
  const byModel = {};
  const completedCasesByModel = {};

  for (const file of files) {
    const entries = await readJsonLines(path.join(directory, file));
    const scoredRows = entries
      .map((entry) => entry?.score ?? null)
      .filter(Boolean);
    if (!scoredRows.length) continue;

    const model =
      scoredRows.find((row) => row.model)?.model ??
      entries.find((entry) => entry?.result?.model)?.result?.model ??
      file.replace(/\.jsonl$/, "");

    byModel[model] = scoredRows;
    completedCasesByModel[model] = scoredRows.length;
  }

  return { byModel, completedCasesByModel };
}

async function summarizeRun(directory, metadata = {}) {
  const manifest = await readJson(path.join(directory, "manifest.json"));
  const metrics = await readJson(path.join(directory, "metrics.json"));
  const complete = Boolean(manifest && metrics);
  const partial = complete
    ? { byModel: {}, completedCasesByModel: {} }
    : await readPartialEvidence(directory);
  const partialModels = Object.keys(partial.byModel);

  if (!manifest && !metrics && !partialModels.length) return null;

  const key = resultKey(directory);
  const models = Array.isArray(manifest?.models)
    ? manifest.models
    : metrics
      ? Object.keys(metrics)
      : partialModels;

  return {
    key,
    runId: manifest?.run_id ?? path.basename(directory),
    createdAt: manifest?.created_at ?? parseRunDate(path.basename(directory)),
    kind: manifest?.kind ?? metadata.kind ?? "quality",
    dataset: manifest?.dataset ?? manifest?.dataset_id ?? null,
    cases:
      manifest?.cases ??
      Math.max(0, ...Object.values(partial.completedCasesByModel)),
    models,
    source: metadata.source ?? "run",
    suiteId: metadata.suiteId ?? null,
    pairedLatencyKey: metadata.pairedLatencyKey ?? null,
    status: complete ? "complete" : "incomplete",
    completedCasesByModel: partial.completedCasesByModel,
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
  const storedMetrics = await readJson(path.join(directory, "metrics.json"));
  const manifest = await readJson(path.join(directory, "manifest.json"), {});
  const storedFailures = await readJson(path.join(directory, "failures.json"));
  const partial = await readPartialEvidence(directory);

  const metrics = storedMetrics ?? Object.fromEntries(
    Object.entries(partial.byModel)
      .map(([model, rows]) => [model, aggregatePartial(rows)])
      .filter(([, aggregate]) => aggregate),
  );

  const failures = storedFailures ?? Object.fromEntries(
    Object.entries(metrics).map(([model, aggregate]) => [
      model,
      aggregate?.failure_analysis ?? [],
    ]),
  );

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
