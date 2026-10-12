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
