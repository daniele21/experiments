import test from "node:test";
import assert from "node:assert/strict";
import { buildModelDatasetMatrix, matrixMetric, matrixTone } from "../src/v2/capabilityMatrix.js";

const latest={
 healthcare:{datasetId:"healthcare_synthetic_v0.1",models:[
  {modelId:"qwen-4",totalGold:31,positiveRecall:.71,negativeValidated:24,negativeFalsePositiveRate:.2083,
   documents:48,validDocuments:48,runKey:"qwen-run"},
  {modelId:"nemotron-4",totalGold:31,positiveRecall:.419,negativeValidated:24,negativeFalsePositiveRate:.0417,
   documents:48,validDocuments:46,runKey:"nemotron-run"},
 ]},
 ambiguous:{datasetId:"ambiguous_synthetic_v0.1",models:[
  {modelId:"nemotron-4",totalGold:24,positiveRecall:.66,negativeValidated:24,negativeFalsePositiveRate:0,
   documents:48,validDocuments:48,runKey:"nemotron-amb"},
 ]},
};

test("matrix is union of models from different suites, columns in benchmark order",()=>{
 const matrix=buildModelDatasetMatrix(latest);
 assert.deepEqual(matrix.datasets.map(d=>d.id),["realistic","challenge","healthcare","ambiguous"]);
 assert.deepEqual(matrix.rows.map(r=>r.modelId),["nemotron-4","qwen-4"]);
 assert.equal(matrix.measured,3);
 assert.equal(matrix.rows[0].cells.healthcare.runKey,"nemotron-run");
 assert.equal(matrix.rows[0].cells.ambiguous.runKey,"nemotron-amb");
 assert.equal(matrix.rows[1].cells.ambiguous,null);
 assert.equal(matrix.rows[1].cells.realistic,null);
});
test("one metric at a time, never zero for undefined negatives or dataset",()=>{
 const m=latest.healthcare.models[0];
 assert.equal(matrixMetric(m,"recall"),.71);
 assert.equal(matrixMetric(m,"fp"),.2083);
 assert.equal(matrixMetric(m,"coverage"),1);
 assert.equal(matrixMetric({...m,negativeValidated:0},"fp"),null);
 assert.equal(matrixMetric({...m,totalGold:0},"recall"),null);
 assert.equal(matrixMetric(null,"recall"),null);
 assert.equal(matrixMetric({...m,documents:0},"coverage"),null);
 assert.equal(matrixMetric(m,"latency"),null);
});
test("uniform absolute performance thresholds and inverse false-positive direction",()=>{
 assert.equal(matrixTone(.93,"recall"),"good");
 assert.equal(matrixTone(.84,"recall"),"medium");
 assert.equal(matrixTone(.40,"recall"),"low");
 assert.equal(matrixTone(.02,"fp"),"good");
 assert.equal(matrixTone(.12,"fp"),"medium");
 assert.equal(matrixTone(.38,"fp"),"low");
 assert.equal(matrixTone(.96,"coverage"),"medium");
 assert.equal(matrixTone(null,"recall"),"unavailable");
});
test("new future model appears without code changes and empty dataset is explicit",()=>{
 const next=buildModelDatasetMatrix({
   ...latest,realistic:{models:[{modelId:"brand-new-19b",totalGold:10,positiveRecall:.9}]},
 });
 assert.equal(next.rows.length,3);
 assert.equal(next.rows.find(r=>r.modelId==="brand-new-19b").cells.healthcare,null);
 assert.equal(buildModelDatasetMatrix({}).rows.length,0);
});
