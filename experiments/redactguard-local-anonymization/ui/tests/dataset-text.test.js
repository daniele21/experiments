import test from "node:test";
import assert from "node:assert/strict";
import { bundledDatasetTextPath, indexBenchmarkTexts } from "../src/v2/datasetText.js";

test("only known bundled synthetic datasets expose text previews", () => {
 assert.equal(bundledDatasetTextPath("healthcare_synthetic_v0.1"), "data/healthcare/cases.jsonl");
 assert.equal(bundledDatasetTextPath("ambiguous_synthetic_v0.1"), "data/ambiguous/cases.jsonl");
 assert.equal(bundledDatasetTextPath("challenge_v0.1"), "data/challenge/cases.jsonl");
 assert.equal(bundledDatasetTextPath("../../private/records.jsonl"), null);
 assert.equal(bundledDatasetTextPath("unknown"), null);
 assert.equal(bundledDatasetTextPath("__proto__"), null);
});
test("preserves exact canonical text and safely ignores malformed rows", () => {
 const texts=indexBenchmarkTexts([{id:"a-pos",text:"Sperimentazione HbA1c 7,2%."},
   {id:"a-neg",text:"Manuale tecnico."},{id:"a-pos",text:"changed"},{id:"no-text"}]);
 assert.equal(texts.get("a-pos"),"Sperimentazione HbA1c 7,2%.");
 assert.equal(texts.get("a-neg"),"Manuale tecnico.");
 assert.equal(texts.size,2);
});
