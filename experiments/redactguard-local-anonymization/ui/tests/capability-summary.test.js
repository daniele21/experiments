import test from "node:test";
import assert from "node:assert/strict";
import {capabilityFromDataset,summarizeCapabilitySuite,selectLatestCapabilityRuns} from "../src/v2/capabilitySummary.js";

const sample={
  qwen4:{
    by_document:{
      "x-pos":{gold_count:3,tp:2,system_tp:2,quality_available:true,human_reviewed:false},
      "x-neg":{gold_count:0,fp:1,system_fp:1,quality_available:true,human_reviewed:false},
      "y-pos":{gold_count:1,tp:1,system_tp:1,quality_available:true,human_reviewed:false},
      "y-neg":{gold_count:0,fp:0,quality_available:true,human_reviewed:false},
      "z-neg":{gold_count:0,fp:0,inference_failures:1,quality_available:false,human_reviewed:false},
    },
    macro_family:{system_pii_recall:.75},
    by_type:{health_condition:{gold_count:3,pii_recall:2/3,fn:1},account_number:{gold_count:1,pii_recall:1,fn:0}},
  },
};
test("categorizes datasets by suite identity without invented scores",()=>{
 assert.equal(capabilityFromDataset("healthcare_synthetic_v0.1"),"healthcare");
 assert.equal(capabilityFromDataset("ambiguous_synthetic_v0.1"),"ambiguous");
 assert.equal(capabilityFromDataset("redactguard-realistic-documents-v0.2"),"realistic");
 assert.equal(capabilityFromDataset("challenge_v0.1"),"challenge");
 assert.equal(capabilityFromDataset("unknown"),null);
});
test("separates positive recall from error rate on valid gold-empty negatives",()=>{
 const s=summarizeCapabilitySuite({key:"suites/s1/quality",suiteId:"s1",datasetId:"healthcare_synthetic_v0.1"},sample);
 assert.equal(s.category,"healthcare");
 const x=s.models[0];
 assert.equal(x.positiveRecall,.75);
 assert.equal(x.balancedRecall,.75);
 assert.equal(x.negativeFalsePositiveRate,.5);
 assert.equal(x.negativeValidated,2);
 assert.equal(x.incompleteNegatives,1);
 assert.equal(x.reviewedCases,0);
 assert.equal(x.types.length,2);
 assert.equal(x.types[0].type,"health_condition");
});
test("no-negative-data or all failed negatives yield null, not zero FP rate",()=>{
 const s=summarizeCapabilitySuite({key:"k",datasetId:"challenge_v0.1"},{
  m:{by_document:{a:{gold_count:1,tp:1},b:{gold_count:0,quality_available:false,inference_failures:1}}},
 });
 assert.equal(s.models[0].negativeFalsePositiveRate,null);
});
test("latest run per category retained without mixing model cohorts",()=>{
 const latest=selectLatestCapabilityRuns([
  {category:"healthcare",createdAt:"2026-10-10T00:00:00Z",runKey:"old"},
  {category:"healthcare",createdAt:"2026-10-12T00:00:00Z",runKey:"new"},
  {category:"ambiguous",createdAt:"2026-10-11T00:00:00Z",runKey:"amb"},
 ]);
 assert.equal(latest.healthcare.runKey,"new");
 assert.equal(latest.ambiguous.runKey,"amb");
});

test("latest result is selected PER MODEL from independent runs on the same dataset",()=>{
 const reports=[
  {category:"healthcare",datasetId:"healthcare_synthetic_v0.1",
   createdAt:"2026-10-10T10:00:00Z",runKey:"suites/qwen/quality",suiteId:"qwen",
   evaluationSchema:"v3",contractSnapshot:"same-contract",
   models:[
     {modelId:"qwen4",positiveRecall:.92,inputFingerprint:"same-input"},
     {modelId:"qwen9",positiveRecall:.96,inputFingerprint:"same-input"},
   ]},
  {category:"healthcare",datasetId:"healthcare_synthetic_v0.1",
   createdAt:"2026-10-13T08:00:00Z",runKey:"suites/nemotron/quality",suiteId:"nemotron",
   evaluationSchema:"v3",contractSnapshot:"same-contract",
   models:[
     {modelId:"nemotron-q4",positiveRecall:.73,inputFingerprint:"same-input"},
     {modelId:"nemotron-q8",positiveRecall:.79,inputFingerprint:"same-input"},
   ]},
 ];
 const merged=selectLatestCapabilityRuns(reports);
 assert.equal(merged.healthcare.models.length,4);
 assert.equal(merged.healthcare.mergedRunCount,2);
 assert.equal(merged.healthcare.runKey,"suites/nemotron/quality");
 const models=Object.fromEntries(merged.healthcare.models.map(m=>[m.modelId,m]));
 assert.equal(models.qwen4.runKey,"suites/qwen/quality");
 assert.equal(models["nemotron-q8"].runKey,"suites/nemotron/quality");
 assert.equal(models.qwen9.positiveRecall,.96);
 assert.equal(models.qwen4.comparability,"verified");
 assert.equal(models["nemotron-q4"].comparability,"reference");
});

test("newest result replaces older result of same model, not the other model",()=>{
 const latest=selectLatestCapabilityRuns([
  {category:"ambiguous",datasetId:"ambiguous_synthetic_v0.1",createdAt:"2026-10-11T00:00:00Z",
   runKey:"old",models:[{modelId:"qwen4",positiveRecall:.50},{modelId:"qwen9",positiveRecall:.85}]},
  {category:"ambiguous",datasetId:"ambiguous_synthetic_v0.1",createdAt:"2026-10-13T00:00:00Z",
   runKey:"new",models:[{modelId:"qwen4",positiveRecall:.90}]},
 ]);
 assert.equal(latest.ambiguous.models.length,2);
 assert.equal(latest.ambiguous.models.find(m=>m.modelId==="qwen4").positiveRecall,.90);
 assert.equal(latest.ambiguous.models.find(m=>m.modelId==="qwen9").runKey,"old");
});

test("different dataset versions aren't silently pooled; configuration differences are labeled",()=>{
 const selected=selectLatestCapabilityRuns([
  {category:"healthcare",datasetId:"healthcare_synthetic_v0.2",createdAt:"2026-10-13T10:00:00Z",
   runKey:"v2",evaluationSchema:"v3",contractSnapshot:"new",
   models:[{modelId:"qwen4",inputFingerprint:"gold-v2"}]},
  {category:"healthcare",datasetId:"healthcare_synthetic_v0.2",createdAt:"2026-10-12T10:00:00Z",
   runKey:"v2-old",evaluationSchema:"v3",contractSnapshot:"old",
   models:[{modelId:"nemotron4",inputFingerprint:"gold-v2"}]},
  {category:"healthcare",datasetId:"healthcare_synthetic_v0.1",createdAt:"2026-10-11T10:00:00Z",
   runKey:"v1",evaluationSchema:"v3",contractSnapshot:"new",
   models:[{modelId:"qwen9",inputFingerprint:"gold-v1"}]},
 ]);
 const active=selected.healthcare;
 assert.deepEqual(active.excludedDatasetVersions,["healthcare_synthetic_v0.1"]);
 assert.equal(active.models.length,2);
 assert.equal(active.models.find(m=>m.modelId==="nemotron4").comparability,"different_protocol");
});
