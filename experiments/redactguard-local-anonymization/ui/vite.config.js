import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const UI_ROOT = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_ROOT = path.resolve(UI_ROOT, "../results");
const SUITE_CONTAINERS = ["suite", "suites"];
const RESERVED_JSONL = new Set(["history.jsonl"]);
const CURRENT_SCHEMA = "redactguard-evaluation-v3";

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

  const isV3 = rows.some(
    (row) =>
      Object.prototype.hasOwnProperty.call(row, "inference_status") ||
      Object.prototype.hasOwnProperty.call(row, "quality_available"),
  );
  const validRows = rows.filter((row) => row.valid);
  const qualityRows = isV3 ? validRows : rows;
  const sum = (source, key) =>
    source.reduce((total, row) => total + Number(row[key] ?? 0), 0);

  const tp = sum(qualityRows, "tp");
  const fp = sum(qualityRows, "fp");
  const fn = sum(qualityRows, "fn");
  const exactTp = sum(qualityRows, "exact_tp");
  const qualityGoldCount = sum(qualityRows, "gold_count");
  const totalGoldCount = sum(rows, "gold_count");
  const predictedCount = sum(qualityRows, "predicted_count");
  const qualityGoldChars = sum(qualityRows, "gold_chars");
  const leakedChars = sum(qualityRows, "leaked_chars");
  const overredactedChars = sum(qualityRows, "overredacted_chars");
  const nonPiiChars = sum(qualityRows, "non_pii_chars");
  const qualityAvailable = !isV3 || validRows.length > 0;
  const recall = qualityAvailable ? ratio(tp, tp + fn, 1) : null;
  const precision = qualityAvailable
    ? ratio(tp, tp + fp, isV3 ? null : 1)
    : null;
  const spanF1 =
    precision === null || recall === null
      ? null
      : precision + recall
        ? (2 * precision * recall) / (precision + recall)
        : 0;

  const systemTp = isV3 ? sum(rows, "system_tp") : tp;
  const systemFp = isV3 ? sum(rows, "system_fp") : fp;
  const systemFn = isV3 ? sum(rows, "system_fn") : fn;
  const systemGoldChars = sum(rows, "gold_chars");
  const systemLeakedChars = isV3 ? sum(rows, "system_leaked_chars") : leakedChars;
  const systemRecall = ratio(systemTp, systemTp + systemFn, 1);
  const systemLeakage = ratio(systemLeakedChars, systemGoldChars);

  const byTypeCounters = new Map();
  for (const row of qualityRows) {
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
    const typePrecision = ratio(
      counts.tp,
      counts.tp + counts.fp,
      isV3 ? null : 1,
    );
    byType[piiType] = {
      ...counts,
      pii_recall: typeRecall,
      precision: typePrecision,
      span_f1:
        typePrecision === null
          ? null
          : typePrecision + typeRecall
            ? (2 * typePrecision * typeRecall) / (typePrecision + typeRecall)
            : 0,
      exact_match_recall: ratio(counts.exact_tp, counts.gold_count, 1),
      leakage_rate: ratio(counts.leaked_chars, counts.gold_chars),
    };
  }

  const failures = rows
    .filter(
      (row) =>
        !row.valid ||
        Number(row.fn ?? 0) ||
        Number(row.fp ?? 0) ||
        Number(row.leaked_chars ?? 0) ||
        Number(row.overredacted_chars ?? 0) ||
        Number(row.unresolved_item_count ?? 0) ||
        row.error,
    )
    .map((row) => ({
      case_id: row.case_id,
      profile: row.profile,
      quality_available: isV3 ? Boolean(row.valid) : true,
      inference_status: row.inference_status ?? (row.valid ? "success" : "legacy_failure"),
      error_type: row.error_type ?? null,
      pii_recall: row.valid || !isV3 ? row.pii_recall : null,
      precision: row.valid || !isV3 ? row.precision : null,
      leakage_rate: row.valid || !isV3 ? row.leakage_rate : null,
      system_pii_recall: row.system_pii_recall ?? row.pii_recall,
      system_leakage_rate: row.system_leakage_rate ?? row.leakage_rate,
      over_redaction_rate: row.over_redaction_rate,
      fn: row.valid || !isV3 ? row.fn : 0,
      fp: row.valid || !isV3 ? row.fp : 0,
      system_fn: row.system_fn ?? row.fn ?? 0,
      inference_failures: row.valid ? 0 : 1,
      unresolved_item_count: row.unresolved_item_count ?? 0,
      false_negatives: row.valid || !isV3 ? row.false_negatives ?? [] : [],
      false_positives: row.valid || !isV3 ? row.false_positives ?? [] : [],
      error: row.error ?? null,
    }));

  const latencies = validRows
    .map((row) => Number(row.latency_ms))
    .filter((value) => Number.isFinite(value));
  const rawItems = sum(validRows, "raw_item_count");
  const resolvedItems = sum(validRows, "resolved_item_count");
  const unresolvedItems = sum(validRows, "unresolved_item_count");
  const statuses = {};
  for (const row of rows) {
    const status = row.inference_status ?? (row.valid ? "success" : "legacy_failure");
    statuses[status] = (statuses[status] ?? 0) + 1;
  }

  const micro = {
    status: isV3 && !validRows.length ? "no_valid_inference" : "ok",
    quality_available: qualityAvailable,
    cases: rows.length,
    evaluated_cases: isV3 ? validRows.length : rows.length,
    inference_failures: rows.length - validRows.length,
    inference_success_rate: ratio(validRows.length, rows.length),
    evaluated_case_coverage: isV3 ? ratio(validRows.length, rows.length) : 1,
    valid_output_rate: ratio(validRows.length, rows.length),
    contract_valid_rate: ratio(validRows.length, rows.length),
    truncation_rate: ratio(statuses.truncated_output ?? 0, rows.length),
    inference_statuses: statuses,
    gold_count: totalGoldCount,
    quality_gold_count: qualityGoldCount,
    predicted_count: predictedCount,
    raw_item_count: rawItems,
    resolved_item_count: resolvedItems,
    unresolved_item_count: unresolvedItems,
    span_resolution_rate: rawItems ? resolvedItems / rawItems : qualityAvailable ? 1 : null,
    tp,
    exact_tp: exactTp,
    fp,
    fn,
    pii_recall: recall,
    precision,
    span_f1: spanF1,
    exact_match_recall: qualityAvailable
      ? ratio(exactTp, qualityGoldCount, 1)
      : null,
    leakage_rate: qualityAvailable
      ? ratio(leakedChars, qualityGoldChars)
      : null,
    zero_leak_document_rate: qualityAvailable
      ? ratio(
          qualityRows.filter((row) => Boolean(row.zero_leak)).length,
          qualityRows.length,
        )
      : null,
    over_redaction_rate: qualityAvailable
      ? ratio(overredactedChars, nonPiiChars)
      : null,
    leaked_chars: leakedChars,
    gold_chars: qualityGoldChars,
    overredacted_chars: overredactedChars,
    non_pii_chars: nonPiiChars,
    latency_p50_ms: percentile(latencies, 0.5),
    latency_p95_ms: percentile(latencies, 0.95),
    latency_p99_ms: percentile(latencies, 0.99),
    failures: rows.length - validRows.length,
    system_tp: systemTp,
    system_fp: systemFp,
    system_fn: systemFn,
    system_pii_recall: systemRecall,
    system_leakage_rate: systemLeakage,
    system_zero_leak_document_rate: ratio(
      rows.filter(
        (row) =>
          row.valid &&
          Number(row.system_fn ?? row.fn ?? 0) === 0 &&
          Number(row.system_leaked_chars ?? row.leaked_chars ?? 0) === 0,
      ).length,
      rows.length,
    ),
  };

  const byDocument = {};
  for (const row of rows) {
    if (!row.case_id) continue;
    byDocument[row.case_id] = {
      cases: 1,
      valid_output_rate: row.valid ? 1 : 0,
      gold_count: row.gold_count ?? 0,
      predicted_count: row.predicted_count ?? 0,
      tp: row.tp ?? 0,
      exact_tp: row.exact_tp ?? 0,
      fp: row.fp ?? 0,
      fn: row.fn ?? 0,
      pii_recall: row.pii_recall ?? ratio(row.tp, (row.tp ?? 0) + (row.fn ?? 0), 1),
      precision: row.precision ?? ratio(row.tp, (row.tp ?? 0) + (row.fp ?? 0), 1),
      span_f1: row.span_f1 ?? 0,
      exact_match_recall: row.exact_match_recall ?? 0,
      leakage_rate: row.leakage_rate ?? ratio(row.leaked_chars, row.gold_chars),
      zero_leak_document_rate: row.zero_leak ? 1 : 0,
      over_redaction_rate: row.over_redaction_rate ?? 0,
      leaked_chars: row.leaked_chars ?? 0,
      gold_chars: row.gold_chars ?? 0,
      overredacted_chars: row.overredacted_chars ?? 0,
      latency_p50_ms: row.latency_ms ?? null,
      latency_p95_ms: row.latency_ms ?? null,
      profile: row.profile ?? null,
      tags: row.tags ?? [],
      false_negatives: row.false_negatives ?? [],
      false_positives: row.false_positives ?? [],
    };
  }

  return {
    ...micro,
    evaluation_schema: isV3
      ? `${CURRENT_SCHEMA}-partial`
      : "redactguard-evaluation-v2-partial",
    micro,
    macro: {},
    by_type: byType,
    by_profile: {},
    by_document: byDocument,
    dataset_balance: {},
    failure_analysis: failures,
  };
}

async function readPartialEvidence(directory) {
  const files = await listModelJsonlFiles(directory);
  const byModel = {};
  const completedCasesByModel = {};
  const schemaByModel = {};

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
    schemaByModel[model] = scoredRows.some(
      (row) =>
        Object.prototype.hasOwnProperty.call(row, "inference_status") ||
        Object.prototype.hasOwnProperty.call(row, "quality_available"),
    )
      ? `${CURRENT_SCHEMA}-partial`
      : "redactguard-evaluation-v2-partial";
  }

  return { byModel, completedCasesByModel, schemaByModel };
}

async function summarizeRun(directory, metadata = {}) {
  const manifest = await readJson(path.join(directory, "manifest.json"));
  const metrics = await readJson(path.join(directory, "metrics.json"));
  const complete = Boolean(manifest && metrics);
  const partial = complete
    ? { byModel: {}, completedCasesByModel: {}, schemaByModel: {} }
    : await readPartialEvidence(directory);
  const partialModels = Object.keys(partial.byModel);

  if (!manifest && !metrics && !partialModels.length) return null;

  const key = resultKey(directory);
  const models = Array.isArray(manifest?.models)
    ? manifest.models
    : metrics
      ? Object.keys(metrics)
      : partialModels;

  const evaluationSchema =
    manifest?.evaluation_schema ??
    partial.schemaByModel?.[partialModels[0]] ??
    null;
  const legacy = !String(evaluationSchema ?? "").startsWith(CURRENT_SCHEMA);

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
    evaluationSchema,
    contractVersion: manifest?.redactguard_contract?.version ?? null,
    legacy,
  };
}

async function discoverRuns() {
  const runs = [];
  const rootDirectories = await listDirectories(RESULTS_ROOT);

  for (const name of rootDirectories) {
    if (SUITE_CONTAINERS.includes(name) || name.endsWith(".backup") || name.startsWith(".")) continue;
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

async function loadDocumentSpans(directory) {
  const docSpans = {};
  try {
    const dirents = await fs.readdir(directory, { withFileTypes: true });
    for (const dirent of dirents) {
      if (!dirent.isFile() || !dirent.name.endsWith(".jsonl") || RESERVED_JSONL.has(dirent.name)) {
        continue;
      }
      const model = dirent.name.replace(".jsonl", "");
      const rows = await readJsonLines(path.join(directory, dirent.name));
      for (const row of rows) {
        const caseId = row.case?.id ?? row.case_id;
        if (!caseId) continue;
        if (!docSpans[caseId]) {
          docSpans[caseId] = {
            gold: (row.case?.gold || []).map((g) => ({
              pii_type: g.pii_type,
              value: g.value,
              start: g.start,
              end: g.end,
            })),
            models: {},
          };
        }
        const missed = (row.score?.false_negatives || []).map((f) => ({
          pii_type: f.pii_type,
          value: f.value,
          start: f.start,
          end: f.end,
        }));
        const overRedacted = (row.score?.false_positives || []).map((f) => ({
          pii_type: f.pii_type,
          value: f.value,
          start: f.start,
          end: f.end,
        }));
        const missedKeys = new Set(
          missed.map((m) => `${m.start}:${m.end}:${m.pii_type}:${m.value}`),
        );
        const identified = docSpans[caseId].gold.filter(
          (g) => !missedKeys.has(`${g.start}:${g.end}:${g.pii_type}:${g.value}`),
        );

        docSpans[caseId].models[model] = {
          valid: row.score?.valid ?? false,
          status: row.score?.inference_status ?? (row.score?.valid ? "success" : "failed"),
          error: row.result?.error || row.score?.error || null,
          recall: row.score?.pii_recall ?? null,
          precision: row.score?.precision ?? null,
          leakage: row.score?.leakage_rate ?? null,
          identifiedCount: identified.length,
          missedCount: missed.length,
          overRedactedCount: overRedacted.length,
          identified: identified.slice(0, 100),
          missed: missed.slice(0, 100),
          overRedacted: overRedacted.slice(0, 100),
        };
      }
    }
  } catch (err) {
    console.error("Error reading document spans:", err);
  }
  return docSpans;
}

async function loadRunFromSummary(summary) {
  const key = summary.key;
  const directory = path.resolve(RESULTS_ROOT, ...key.split("/"));
  const storedMetrics = await readJson(path.join(directory, "metrics.json"));
  const manifest = await readJson(path.join(directory, "manifest.json"), {});
  const storedFailures = await readJson(path.join(directory, "failures.json"));
  const partial = storedMetrics
    ? { byModel: {}, completedCasesByModel: {}, schemaByModel: {} }
    : await readPartialEvidence(directory);

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

  const preflight = await readJson(path.join(directory, "preflight.json"), {});
  const docSpans = await loadDocumentSpans(directory);
  return { summary, manifest, metrics, failures, latency, preflight, docSpans };
}

async function loadRun(key) {
  const runs = await discoverRuns();
  const summary = runs.find((item) => item.key === key);
  if (!summary) return null;
  return loadRunFromSummary(summary);
}

function evidenceCases(summary, model, metrics) {
  return (
    summary.completedCasesByModel?.[model] ??
    metrics?.micro?.cases ??
    metrics?.cases ??
    summary.cases ??
    null
  );
}

async function buildOverview() {
  const runs = await discoverRuns();
  const bestByModel = new Map();

  function candidateTier(run) {
    if (!run.legacy && run.status === "complete") return 0;
    if (!run.legacy && run.status === "incomplete") return 1;
    if (run.legacy && run.status === "complete") return 2;
    return 3;
  }

  function isBetterCandidate(candidate, current) {
    if (!current) return true;
    const tierCand = candidateTier(candidate.run);
    const tierCurr = candidateTier(current.run);
    if (tierCand !== tierCurr) return tierCand < tierCurr;

    // Prefer run with higher evaluated cases coverage
    const candCases =
      candidate.metrics?.micro?.evaluated_cases ?? candidate.metrics?.cases ?? 0;
    const currCases =
      current.metrics?.micro?.evaluated_cases ?? current.metrics?.cases ?? 0;
    if (candCases !== currCases) return candCases > currCases;

    // If tier and coverage are identical, prefer the more recent run
    const timeCand = Date.parse(candidate.run.createdAt ?? "") || 0;
    const timeCurr = Date.parse(current.run.createdAt ?? "") || 0;
    return timeCand > timeCurr;
  }

  for (const run of runs) {
    if (run.kind === "latency") continue;
    const detail = await loadRunFromSummary(run);

    for (const [model, metrics] of Object.entries(detail.metrics ?? {})) {
      if (!metrics) continue;

      const candidate = {
        run,
        metrics,
        failures: detail.failures?.[model] ?? [],
        latencyMetrics: detail.latency?.metrics?.[model] ?? null,
        preflight: detail.preflight?.[model] ?? metrics?.preflight ?? null,
      };
      const current = bestByModel.get(model);
      if (isBetterCandidate(candidate, current)) {
        bestByModel.set(model, candidate);
      }
    }
  }

  const modelNames = [...bestByModel.keys()].sort();
  const metrics = {};
  const failures = {};
  const latencyMetrics = {};
  const evidence = {};

  for (const model of modelNames) {
    const candidate = bestByModel.get(model);
    if (!candidate) continue;

    metrics[model] = candidate.metrics;
    failures[model] = candidate.failures;
    if (candidate.latencyMetrics) latencyMetrics[model] = candidate.latencyMetrics;

    const modelMicro = candidate.metrics?.micro ?? candidate.metrics ?? {};
    evidence[model] = {
      runKey: candidate.run.key,
      runId: candidate.run.runId,
      suiteId: candidate.run.suiteId,
      createdAt: candidate.run.createdAt,
      status: candidate.run.status,
      dataset: candidate.run.dataset,
      source: candidate.run.source,
      cases: evidenceCases(candidate.run, model, candidate.metrics),
      evaluatedCases: modelMicro.evaluated_cases ?? null,
      latencySource: candidate.latencyMetrics ? "dedicated" : "quality-run",
      evaluationSchema: candidate.run.evaluationSchema,
      contractVersion: candidate.run.contractVersion,
      legacy: candidate.run.legacy,
      contractStatus:
        modelMicro.status === "contract_failed"
          ? "failed"
          : candidate.run.legacy
            ? "legacy"
            : "passed",
      qualityAvailable: modelMicro.quality_available ?? !candidate.run.legacy,
      preflight: candidate.preflight,
    };
  }

  const docSpans = {};
  for (const [model, candidate] of bestByModel.entries()) {
    const candidateDirectory = path.resolve(
      RESULTS_ROOT,
      ...candidate.run.key.split("/"),
    );
    const candidateDocSpans = await loadDocumentSpans(candidateDirectory);
    for (const [caseId, data] of Object.entries(candidateDocSpans)) {
      if (!docSpans[caseId]) {
        docSpans[caseId] = { gold: data.gold, models: {} };
      }
      if (data.models[model]) {
        docSpans[caseId].models[model] = data.models[model];
      }
    }
  }

  const statuses = Object.values(evidence);
  const datasets = [...new Set(
    statuses.map((item) => item.dataset).filter(Boolean),
  )];

  return {
    summary: {
      key: "__overview__",
      runId: "Unified overview",
      createdAt: runs[0]?.createdAt ?? null,
      kind: "overview",
      dataset: datasets.length === 1 ? datasets[0] : null,
      models: modelNames,
      source: "overview",
      status: statuses.some((item) => item.status === "incomplete")
        ? "mixed"
        : "complete",
      completeModels: statuses.filter((item) => item.status === "complete").length,
      partialModels: statuses.filter((item) => item.status === "incomplete").length,
      legacyModels: statuses.filter((item) => item.legacy).length,
      contractFailedModels: statuses.filter(
        (item) => item.contractStatus === "failed",
      ).length,
      sourceRuns: new Set(statuses.map((item) => item.runKey)).size,
      datasets,
    },
    manifest: {},
    metrics,
    failures,
    latency: { metrics: latencyMetrics },
    evidence,
    docSpans,
  };
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

      if (url.pathname === "/api/overview") {
        sendJson(response, 200, await buildOverview());
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
