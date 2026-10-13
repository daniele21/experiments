// The UI may load canonical texts only from explicitly bundled, public,
// synthetic benchmark files. Never resolve arbitrary paths from suite metadata.
const DATASET_TEXT_SOURCE = Object.freeze({
  "healthcare_synthetic_v0.1": "data/healthcare/cases.jsonl",
  "ambiguous_synthetic_v0.1": "data/ambiguous/cases.jsonl",
  "challenge_v0.1": "data/challenge/cases.jsonl",
});

export function bundledDatasetTextPath(datasetId) {
  return Object.prototype.hasOwnProperty.call(DATASET_TEXT_SOURCE, datasetId)
    ? DATASET_TEXT_SOURCE[datasetId] : null;
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
  if (typeof manifestDataset !== "string") return null;
  const normalized = manifestDataset.replaceAll("\\", "/");
  for (const source of Object.values(DATASET_TEXT_SOURCE)) {
    if (normalized === source || normalized.endsWith("/" + source)) return source;
  }
  return null;
}

// When results are read after a repository update, the current dataset text
// may no longer be identical to the bytes used in the actual inference.
// Such texts must not be shown as if their span offsets were trustworthy.
export function textMatchesBenchmarkHash(text, digest) {
  if (typeof text !== "string") return false;
  if (typeof digest !== "string" || !/^[0-9a-f]{64}$/i.test(digest)) return null;
  return null; // Hash comparison is performed with node:crypto in the Vite server.
}

export function canCompareOverviewDocuments(datasetIds) {
  const ids = [...new Set((datasetIds ?? []).filter(Boolean))];
  return ids.length === 1;
}
