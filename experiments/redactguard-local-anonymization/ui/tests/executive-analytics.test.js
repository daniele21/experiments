import test from "node:test";
import assert from "node:assert/strict";
import { nonDominated, privacyFrontier, efficiencyFrontier, summarizeExecutive } from "../src/v2/executiveAnalytics.js";

// Values from the Healthcare screenshot are fixtures, not newly inferred results.
const healthcare={
 datasetId:"healthcare_synthetic_v0.1",
 models:[
  {modelId:"nemotron-q4",runKey:"nano-q4",suiteId:"run-nem",positiveRecall:.419,
   negativeFalsePositiveRate:.042,negativeValidated:24,totalGold:31,validDocuments:46,documents:48,comparability:"reference"},
  {modelId:"nemotron-q8",runKey:"nano-q8",suiteId:"run-nem",positiveRecall:.516,
   negativeFalsePositiveRate:0,negativeValidated:24,totalGold:31,validDocuments:48,documents:48,comparability:"verified"},
  {modelId:"qwen4",runKey:"qwen4",suiteId:"run-qwen",positiveRecall:.710,
   negativeFalsePositiveRate:.208,negativeValidated:24,totalGold:31,validDocuments:48,documents:48,comparability:"verified"},
  {modelId:"qwen9",runKey:"qwen9",suiteId:"run-qwen",positiveRecall:.935,
   negativeFalsePositiveRate:.375,negativeValidated:24,totalGold:31,validDocuments:48,documents:48,comparability:"verified"},
 ],
};
const ids=healthcare.models.map(x=>x.modelId);

test("privacy frontier: Nemotron Q8 dominates Q4; the other two models remain trade-offs",()=>{
 const r=privacyFrontier(healthcare,ids);
 assert.deepEqual(r.frontier.map(p=>p.modelId),["nemotron-q8","qwen4","qwen9"]);
 assert.equal(r.points.find(p=>p.modelId==="nemotron-q4").dominated,true);
 assert.equal(r.excluded,0);
});

test("equal coordinates do not strictly dominate each other",()=>{
 const points=[{id:"A",x:0,y:.85},{id:"B",x:0,y:.85},{id:"C",x:.2,y:.5}];
 assert.deepEqual(nonDominated(points,"x","y").map(x=>x.id),["A","B"]);
});
test("missing negatives, missing recall, or a proven mismatched protocol excludes a model",()=>{
 const report={models:[
  {...healthcare.models[0],modelId:"no-negative",negativeValidated:0,negativeFalsePositiveRate:null},
  {...healthcare.models[1],modelId:"mismatched",comparability:"different_protocol"},
  {...healthcare.models[2],modelId:"no-recall",totalGold:0,positiveRecall:null},
 ]};
 const r=privacyFrontier(report,report.models.map(m=>m.modelId));
 assert.equal(r.eligible,0);
 assert.equal(r.excluded,3);
 assert.equal(r.frontier.length,0);
});
test("filtering models recalculates frontier, not a static global ranking",()=>{
 const r=privacyFrontier(healthcare,["nemotron-q4","qwen4"]);
 assert.equal(r.frontier.length,2);
 assert.equal(r.points.length,2);
});
test("efficiency Pareto requires paired cache-off verified latency within SAME suite",()=>{
 const report={models:[
   {modelId:"a",suiteId:"A",runKey:"a",positiveRecall:.8,
    latencyVerified:true,p50Ms:4200,latencyProtocol:"hash-workload-A",latencySamples:15},
   {modelId:"b",suiteId:"A",runKey:"b",positiveRecall:.9,
    latencyVerified:true,p50Ms:7200,latencyProtocol:"hash-workload-A",latencySamples:15},
   {modelId:"c",suiteId:"A",runKey:"c",positiveRecall:.7,
    latencyVerified:true,p50Ms:8000,latencyProtocol:"hash-workload-A",latencySamples:15},
   {modelId:"d",suiteId:"B",runKey:"d",positiveRecall:1,
    latencyVerified:true,p50Ms:5,latencyProtocol:"hash-workload-A",latencySamples:15},
   {modelId:"e",suiteId:"A",runKey:"e",positiveRecall:.5,
    latencyVerified:false,p50Ms:1,latencyProtocol:"hash-workload-A"},
   {modelId:"f",suiteId:"A",runKey:"f",positiveRecall:.99,
    latencyVerified:true,p50Ms:4000,latencyProtocol:"another-workload",latencySamples:15},
 ]};
 const r=efficiencyFrontier(report,report.models.map(m=>m.modelId));
 assert.equal(r.valid,true);
 assert.deepEqual(r.frontier.map(p=>p.modelId),["a","b"]);
 assert.deepEqual(r.points.map(p=>p.modelId),["a","b","c"]);
 assert.equal(r.points.find(p=>p.modelId==="c").dominated,true);
 assert.equal(r.excluded,3);
});
test("no cache-off latency on quality-only suites: show no fabricated efficiency frontier",()=>{
 const r=efficiencyFrontier(healthcare,ids);
 assert.equal(r.valid,false);
 assert.equal(r.points.length,0);
 const e=summarizeExecutive({healthcare},"healthcare",ids,"efficiency");
 assert.match(e.advisory,/stessa suite/);
});
test("executive insight is tied to selected dataset and selected models",()=>{
 const e=summarizeExecutive({healthcare},"healthcare",["nemotron-q4","qwen4"],"privacy");
 assert.equal(e.bestRecall.modelId,"qwen4");
 assert.equal(e.leastOverredaction.modelId,"nemotron-q4");
 assert.equal(e.fullyValid,1);
 assert.equal(e.goldReviewed,false);
});

test("incompatible run cannot become executive best-model recommendation",()=>{
 const mismatch={
  ...healthcare,
  models:healthcare.models.map(m=>m.modelId==="qwen9"
   ? {...m,comparability:"different_protocol"} : m),
 };
 const r=summarizeExecutive({healthcare:mismatch},"healthcare",ids,"privacy");
 assert.equal(r.bestRecall.modelId,"qwen4");
 assert.equal(r.frontier.points.find(p=>p.modelId==="qwen9").eligible,false);
 assert.equal(r.frontier.excluded,1);
});
