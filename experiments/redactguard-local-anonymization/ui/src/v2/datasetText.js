// Source lookup is a fixed allowlist: bundled synthetic data and opt-in
// local caches (E3C, ASQ-PHI, MEDDOCAN, PharmaER, SPACCC). Never resolve arbitrary paths from suite metadata.
const DATASET_TEXT_SOURCE = Object.freeze({
  "healthcare_synthetic_v0.1": "data/healthcare/cases.jsonl",
  "ambiguous_synthetic_v0.1": "data/ambiguous/cases.jsonl",
  "challenge_v0.1": "data/challenge/cases.jsonl",
  "e3c_it_v2_injected_pii_v1": "data/cache/e3c-it-v2/synthetic_pii.jsonl",
  "asq_phi_hipaa_13_v1": "data/cache/asq-phi-v1/cases.jsonl",
  "meddocan_test_brat_coarse_v1": "data/cache/meddocan-test-v1/cases.jsonl",
  "pharmaer_it_gold_test_v03": "data/cache/pharmaer-it-gold-test-v03/cases.jsonl",
  "spaccc_es_clinical_gold_v1": "data/cache/spaccc-clinical-gold-v1/cases.jsonl",
  "e3c_it_clinical_gold_v1": "data/cache/e3c-it-clinical-gold-v1/cases.jsonl",
});

export function bundledDatasetTextPath(datasetId) {
  if (typeof datasetId !== "string") return null;
  if (Object.prototype.hasOwnProperty.call(DATASET_TEXT_SOURCE, datasetId)) {
    return DATASET_TEXT_SOURCE[datasetId];
  }
  for (const [key, source] of Object.entries(DATASET_TEXT_SOURCE)) {
    if (datasetId.startsWith(key + "-")) return source;
  }
  return null;
}

export function indexBenchmarkTexts(rows) {
  const lookup = new Map();
  for (const row of rows ?? []) {
    if (typeof row?.id !== "string" || typeof row?.text !== "string") continue;
    if (!lookup.has(row.id)) lookup.set(row.id, row.text);
  }
  return lookup;
}


// A suite can be opened from its own manifest, a standalone quality run,
// or a unified overview. Prefer the pinned dataset ID; fall back only to an
// EXACT known dataset filename suffix, never open paths from untrusted metadata.
export function resolveBundledDatasetSource(datasetId, manifestDataset) {
  const fromId = bundledDatasetTextPath(datasetId);
  if (fromId) return fromId;
  if (typeof manifestDataset !== "string" || /^[a-z][a-z0-9+.-]*:\/\//i.test(manifestDataset)) return null;
  const normalized = manifestDataset.replaceAll("\\", "/");
  for (const source of Object.values(DATASET_TEXT_SOURCE)) {
    if (normalized === source || normalized.endsWith("/" + source)) return source;
  }
  return null;
}

export function canCompareOverviewDocuments(datasetIds) {
  const ids = [...new Set((datasetIds ?? []).filter(Boolean))];
  return ids.length === 1;
}
