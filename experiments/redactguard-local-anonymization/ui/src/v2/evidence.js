// RedactBench UI 2.0 — read-only evidence selectors shared by all three views.
// Never synthesize missing measurements or rank mixed/legacy suites as identical.
export const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
export const ratioText = (value, digits = 1) =>
  isNumber(value) ? `${(value * 100).toFixed(digits)}%` : "—";
export const timeText = (ms) =>
  isNumber(ms) ? (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms.toFixed(0)} ms`) : "—";
export const shortModel = (name) =>
  String(name ?? "").replace(/-q4km$/i, " · Q4_K_M").replace(/-q8$/i, " · Q8").replace(/-q4$/i, " · Q4");
export const modelsIn = (detail) =>
  detail?.summary?.models?.length ? detail.summary.models : Object.keys(detail?.metrics ?? {});
const choose = (...values) => values.find(isNumber) ?? null;
const micro = (value) => value?.micro ?? value ?? {};
export function isSameSuite(detail) {
  return detail?.summary?.source === "suite" &&
    detail.summary.status === "complete" &&
    detail?.suiteMeta?.status === "completed";
}
export function latencyVerified(detail, model) {
  const meta = detail?.suiteMeta;
  const latency = detail?.latency;
  // Old suites with a cache that wasn't explicitly switched off can report
  // 2ms "inference". Treat those as unavailable, not as a huge speed win.
  return isSameSuite(detail) &&
    meta?.inference_cache_max_entries === 0 &&
    latency?.manifest?.kind === "latency" &&
    Array.isArray(latency.manifest.models) &&
    latency.manifest.models.includes(model) &&
    (detail.summary.models ?? []).includes(model) &&
    Boolean(latency?.metrics?.[model]);
}
export function modelEvidence(detail, model) {
  const metrics = detail?.metrics?.[model] ?? {};
  const score = micro(metrics);
  const family = metrics?.macro_family ?? null;
  const docMacro = metrics?.macro ?? null;
  const qualityBase = family ? "family" : docMacro ? "document" : "micro";
  const weighted = family ?? docMacro ?? score;
  const total = choose(score.cases, score.evaluated_cases) ?? 0;
  const valid = choose(score.evaluated_cases, score.cases) ?? 0;
  const zeroRate = choose(score.system_zero_leak_document_rate, score.zero_leak_document_rate);
  const latencyStats = micro(detail?.latency?.metrics?.[model]);
  const verified = latencyVerified(detail, model);
  return {
    model, qualityBase, total, valid,
    recall: choose(weighted.system_pii_recall, weighted.pii_recall),
    microRecall: choose(score.system_pii_recall, score.pii_recall),
    precision: choose(score.precision),
    leakage: choose(weighted.system_leakage_rate, weighted.leakage_rate),
    microLeakage: choose(score.system_leakage_rate, score.leakage_rate),
    zeroRate,
    zeroCount: isNumber(zeroRate) && total ? Math.round(zeroRate * total) : null,
    falseNegatives: choose(score.system_fn, score.fn),
    falsePositives: choose(score.system_fp, score.fp),
    success: choose(score.inference_success_rate, score.valid_output_rate),
    cacheVerified: verified,
    p50: verified ? choose(latencyStats.latency_p50_ms) : null,
    p95: verified ? choose(latencyStats.latency_p95_ms) : null,
    sampleCount: verified ? choose(latencyStats.cases, latencyStats.evaluated_cases) : null,
    latencyCases: verified ? detail?.latency?.manifest?.case_ids?.length ?? null : null,
    humanReviewed: Object.values(metrics?.by_document ?? {}).every(x => x?.human_reviewed === true),
    failures: score.inference_failures ?? null,
  };
}
export function documentEvidence(detail, caseId, models = modelsIn(detail)) {
  const raw = detail?.docSpans?.[caseId] ?? null;
  const metrics = models.map(model => {
    const doc = detail?.metrics?.[model]?.by_document?.[caseId] ?? null;
    const modelRaw = raw?.models?.[model] ?? null;
    const status = !doc && !modelRaw ? "unavailable" : (modelRaw?.valid === false || doc?.quality_available === false || (doc?.inference_failures ?? 0) > 0) ? "failed" : "ok";
    return {
      model, status,
      recall: status === "ok" ? choose(doc?.system_pii_recall, doc?.pii_recall, modelRaw?.recall) : null,
      leakage: status === "ok" ? choose(doc?.system_leakage_rate, doc?.leakage_rate, modelRaw?.leakage) : null,
      tp: status === "ok" ? choose(doc?.system_tp, doc?.tp, modelRaw?.identifiedCount) : null,
      fn: status === "ok" ? choose(doc?.system_fn, doc?.fn, modelRaw?.missedCount) : null,
      fp: status === "ok" ? choose(doc?.system_fp, doc?.fp, modelRaw?.overRedactedCount) : null,
      error: modelRaw?.error ?? doc?.representative_error ?? null,
      raw: modelRaw,
    };
  });
  const primary = models.map(x => detail?.metrics?.[x]?.by_document?.[caseId]).find(Boolean);
  return {
    caseId,
    extension: caseId.includes(".") ? caseId.split(".").at(-1).toLowerCase() : "txt",
    family: primary?.content_family_id ?? caseId,
    goldCount: choose(primary?.gold_count, raw?.gold?.length) ?? 0,
    humanReviewed: primary?.human_reviewed === true,
    text: raw?.text ?? null,
    textStatus: raw?.textStatus ?? "missing_source",
    gold: raw?.gold ?? [],
    metrics,
  };
}
export function allDocuments(detail, models = modelsIn(detail)) {
  const ids = new Set(Object.keys(detail?.docSpans ?? {}));
  for (const model of models)
    for (const name of Object.keys(detail?.metrics?.[model]?.by_document ?? {})) ids.add(name);
  return [...ids].sort().map(id => documentEvidence(detail, id, models));
}
export function spanMatchesText(text, span) {
  if (!text || !Number.isInteger(span?.start) || !Number.isInteger(span?.end) ||
      span.start < 0 || span.end <= span.start || span.end > text.length) return false;
  const actual = text.slice(span.start, span.end);
  // Missing value alone is not proof of a correct offset.
  return typeof span.value === "string" && actual === span.value;
}
export function spanKey(span) {
  return `${span.start}:${span.end}:${span.pii_type ?? ""}`;
}
export function spansForModel(doc, model) {
  const raw = doc?.metrics?.find(m => m.model === model)?.raw;
  const text = doc?.text ?? "";
  if (!raw) return {
    items: [], invalidOffsets: 0, invalidGoldOffsets: 0, invalidExtraOffsets: 0,
  };
  const missed = new Set((raw.missed ?? []).map(spanKey));
  const gold = (doc.gold ?? []).map(g => ({
    ...g, status: missed.has(spanKey(g)) ? "missed" : "detected",
  }));
  const extras = (raw.overRedacted ?? []).map(f => ({...f, status:"extra"}));

  // A mismatched GOLD annotation means the masking boundaries themselves
  // cannot be trusted, so keep the existing fail-closed document preview.
  // By contrast, model-generated false positives can have inaccurate offsets
  // or normalized values: omit only those overlays, retain the valid gold
  // highlights, and report the unpositioned extras in the inspector.
  const validGold = gold.filter(s => spanMatchesText(text, s));
  const validExtras = extras.filter(s => spanMatchesText(text, s));
  const invalidGoldOffsets = gold.length - validGold.length;
  const invalidExtraOffsets = extras.length - validExtras.length;
  const items = [...validGold, ...validExtras];

  // Gold labels must win over overlapping model-generated extras so a
  // false positive never conceals a missed ground-truth annotation.
  const priority = s => s.status === "extra" ? 1 : 0;
  items.sort((a,b) =>
    a.start-b.start || priority(a)-priority(b) ||
    a.end-b.end || a.status.localeCompare(b.status));
  return {
    items,
    invalidGoldOffsets,
    invalidExtraOffsets,
    invalidOffsets: invalidGoldOffsets + invalidExtraOffsets,
  };
}
export function compareInsight(a, b, focus) {
  if (!a || !b) return "Scegli due modelli per confrontarli.";
  if (focus === "speed") {
    if (!isNumber(a.p50) || !isNumber(b.p50)) return "Latenza non verificata per questa coppia.";
    if (Math.abs(a.p50-b.p50) < 1) return "Velocità sostanzialmente equivalente.";
    const faster = a.p50 < b.p50 ? a : b;
    const slower = faster === a ? b : a;
    return `${shortModel(faster.model)} è ${(slower.p50/faster.p50).toFixed(1)}× più veloce nei test di latenza.`;
  }
  if(focus==="tradeoff") return "La scelta dipende dal peso che dai a qualità e tempo di risposta.";
  if (!isNumber(a.zeroRate) || !isNumber(b.zeroRate)) return "Protezione non confrontabile.";
  if(a.zeroRate===b.zeroRate) return "Stesso numero di documenti senza leakage.";
  const best = a.zeroRate > b.zeroRate ? a : b;
  return `${shortModel(best.model)} lascia meno documenti con PII esposte.`;
}
