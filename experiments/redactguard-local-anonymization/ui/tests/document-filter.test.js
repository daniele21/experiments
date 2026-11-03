import test from "node:test";
import assert from "node:assert/strict";
import { documentEvidence, docPiiSummary } from "../src/v2/evidence.js";

const testSuite = {
  summary: { source: "suite", status: "complete", models: ["modelA", "modelB"] },
  suiteMeta: { status: "completed", inference_cache_max_entries: 0 },
  metrics: {
    modelA: {
      by_document: {
        "doc1.txt": { gold_count: 2, pii_recall: 1.0, system_fn: 0, human_reviewed: false },
        "doc2.txt": { gold_count: 2, pii_recall: 0.5, system_fn: 1, human_reviewed: false },
        "doc3.txt": { gold_count: 0, pii_recall: null, system_fn: 0, human_reviewed: false },
      },
    },
    modelB: {
      by_document: {
        "doc1.txt": { gold_count: 2, pii_recall: 1.0, system_fn: 0, human_reviewed: false },
        "doc2.txt": { gold_count: 2, pii_recall: 1.0, system_fn: 0, human_reviewed: false },
        "doc3.txt": { gold_count: 0, pii_recall: null, system_fn: 0, human_reviewed: false },
      },
    },
  },
  docSpans: {
    "doc1.txt": {
      text: "Mario Rossi il 12/04/2023",
      gold: [
        { pii_type: "name", start: 0, end: 11, value: "Mario Rossi" },
        { pii_type: "date", start: 15, end: 25, value: "12/04/2023" },
      ],
      models: {
        modelA: { valid: true, identified: [{ pii_type: "name", value: "Mario Rossi" }, { pii_type: "date", value: "12/04/2023" }], missed: [] },
        modelB: { valid: true, identified: [{ pii_type: "name", value: "Mario Rossi" }, { pii_type: "date", value: "12/04/2023" }], missed: [] },
      },
    },
    "doc2.txt": {
      text: "Cartella clinica MRN-998 per Mario Rossi",
      gold: [
        { pii_type: "name", start: 30, end: 41, value: "Mario Rossi" },
        { pii_type: "medical_record_number", start: 17, end: 24, value: "MRN-998" },
      ],
      models: {
        modelA: { valid: true, identified: [{ pii_type: "name", value: "Mario Rossi" }], missed: [{ pii_type: "medical_record_number", value: "MRN-998" }] },
        modelB: { valid: true, identified: [{ pii_type: "name", value: "Mario Rossi" }, { pii_type: "medical_record_number", value: "MRN-998" }], missed: [] },
      },
    },
    "doc3.txt": {
      text: "Nessuna informazione personale presente.",
      gold: [],
      models: {
        modelA: { valid: true, identified: [], missed: [] },
        modelB: { valid: true, identified: [], missed: [] },
      },
    },
  },
};

test("filters documents by recognized PII type and status correctly", () => {
  const docs = ["doc1.txt", "doc2.txt", "doc3.txt"].map(id =>
    documentEvidence(testSuite, id, ["modelA", "modelB"])
  );
  const summaries = new Map(docs.map(d => [d.caseId, docPiiSummary(d, ["modelA", "modelB"])]));

  // 1. Filter by recognized PII type "medical_record_number"
  const mrnDocs = docs.filter(d => summaries.get(d.caseId).recognizedByType.has("medical_record_number"));
  assert.equal(mrnDocs.length, 1);
  assert.equal(mrnDocs[0].caseId, "doc2.txt");

  // 2. Filter by recognized PII type "name"
  const nameDocs = docs.filter(d => summaries.get(d.caseId).recognizedByType.has("name"));
  assert.equal(nameDocs.length, 2);
  assert.deepEqual(nameDocs.map(d => d.caseId), ["doc1.txt", "doc2.txt"]);

  // 3. Filter by missed PII type "medical_record_number"
  const missedMrn = docs.filter(d => summaries.get(d.caseId).missedByType.has("medical_record_number"));
  assert.equal(missedMrn.length, 1);
  assert.equal(missedMrn[0].caseId, "doc2.txt");

  // 4. Status: all_recognized (100% recall across active models)
  const allRec = docs.filter(d => summaries.get(d.caseId).isAllRecognized);
  assert.equal(allRec.length, 1);
  assert.equal(allRec[0].caseId, "doc1.txt");

  // 5. Status: has_missed (leakage > 0 in at least one model)
  const hasMissed = docs.filter(d => summaries.get(d.caseId).hasMissed);
  assert.equal(hasMissed.length, 1);
  assert.equal(hasMissed[0].caseId, "doc2.txt");

  // 6. Status: zero_gold (hard negatives)
  const zeroGold = docs.filter(d => summaries.get(d.caseId).isZeroGold);
  assert.equal(zeroGold.length, 1);
  assert.equal(zeroGold[0].caseId, "doc3.txt");

  // 7. Comparison: modelB beats modelA
  const bBeatsA = docs.filter(d => (d.metrics[1]?.recall ?? 0) > (d.metrics[0]?.recall ?? 0));
  assert.equal(bBeatsA.length, 1);
  assert.equal(bBeatsA[0].caseId, "doc2.txt");
});

