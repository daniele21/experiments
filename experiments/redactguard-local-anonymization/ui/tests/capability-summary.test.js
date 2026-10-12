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
