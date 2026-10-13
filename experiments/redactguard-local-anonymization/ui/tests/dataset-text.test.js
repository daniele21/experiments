import test from "node:test";
import assert from "node:assert/strict";
import { bundledDatasetTextPath, indexBenchmarkTexts, resolveBundledDatasetSource, canCompareOverviewDocuments } from "../src/v2/datasetText.js";

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


test("standalone and overview runs resolve source only from an exact bundled dataset suffix", () => {
 assert.equal(
   resolveBundledDatasetSource(null, "/Users/demo/experiments/experiments/redactguard-local-anonymization/data/ambiguous/cases.jsonl"),
   "data/ambiguous/cases.jsonl",
 );
 assert.equal(resolveBundledDatasetSource("ambiguous_synthetic_v0.1",null),"data/ambiguous/cases.jsonl");
 assert.equal(resolveBundledDatasetSource(null,"data/healthcare/cases.jsonl"),"data/healthcare/cases.jsonl");
 assert.equal(resolveBundledDatasetSource(null,"../../secrets/cases.jsonl"),null);
 assert.equal(resolveBundledDatasetSource(null,"/tmp/data/ambiguous/cases.jsonl.hacked"),null);
 assert.equal(resolveBundledDatasetSource(null,"http://evil.test/data/ambiguous/cases.jsonl"),"data/ambiguous/cases.jsonl");
});

test("unified document inspection is blocked when selected models came from different datasets", () => {
 assert.equal(canCompareOverviewDocuments(["ambiguous_synthetic_v0.1","healthcare_synthetic_v0.1"]),false);
 assert.equal(canCompareOverviewDocuments(["ambiguous_synthetic_v0.1","ambiguous_synthetic_v0.1"]),true);
 assert.equal(canCompareOverviewDocuments([]),false);
});
