import test from "node:test";
import assert from "node:assert/strict";
import { datasetInfo, groupExperiments, qualityRuns } from "../src/workspace/experimentCatalog.js";

test("clinical datasets are discoverable without pooling their executions", () => {
  const runs = [
    { key:"suites/old/quality",dataset:"/old/mac/data/cache/spaccc-clinical-gold-v1/cases.jsonl",createdAt:"2026-11-03T16:00:00Z",cases:200,models:["qwen4","qwen9"],status:"complete" },
    { key:"suites/new/quality",dataset:"/new/mac/data/cache/spaccc-clinical-gold-v1/cases.jsonl",createdAt:"2026-11-04T09:00:00Z",cases:50,models:["qwen4"],status:"complete" },
    { key:"suites/asq/quality",dataset:"data/cache/asq-phi-v1/cases.jsonl",models:["qwen9"] },
    { key:"suites/e3c/quality",dataset:"data/cache/e3c-it-v2/synthetic_pii.jsonl",models:["qwen4"] },
    { key:"suites/old/latency",kind:"latency",dataset:"data/cache/spaccc-clinical-gold-v1/cases.jsonl",models:["qwen4"] },
  ];
  const groups = groupExperiments(runs);
  assert.deepEqual(new Set(groups.map(g=>g.id)),new Set(["spaccc","asq","e3c"]));
  const spanish=groups.find(g=>g.id==="spaccc");
  assert.deepEqual(spanish.runs.map(r=>r.cases),[50,200]);
  assert.deepEqual(spanish.models,["qwen4","qwen9"]);
  assert.equal(qualityRuns(runs).length,4);
  assert.equal(runs[0].key,"suites/old/quality");
});

test("unknown and partial evidence remains accessible without inventing dataset metadata", () => {
  const runs=[{key:"partial",status:"incomplete",models:["m"]},
    {key:"custom",dataset:"data/cache/future-corpus/cases.jsonl",models:["m"]}];
  const groups=groupExperiments(runs);
  assert.equal(groups.length,2);
  assert.equal(groups.find(g=>g.id==="unknown").runs[0].status,"incomplete");
  assert.equal(datasetInfo(runs[1].dataset).title,"future-corpus");
  assert.equal(datasetInfo(runs[1].dataset).language,null);
});
