import test from "node:test";
import assert from "node:assert/strict";
import {sortExecutiveRows,nextHeatmapSort} from "../src/v2/heatmapSort.js";
const rows=[
 {modelId:"Qwen9",cells:{healthcare:{totalGold:5,positiveRecall:.9,negativeValidated:4,negativeFalsePositiveRate:.35}}},
 {modelId:"Nemotron4",cells:{healthcare:{totalGold:5,positiveRecall:.4,negativeValidated:4,negativeFalsePositiveRate:0}}},
 {modelId:"Qwen4",cells:{healthcare:{totalGold:5,positiveRecall:.7,negativeValidated:4,negativeFalsePositiveRate:.1}}},
 {modelId:"Other",cells:{healthcare:null}},
];
const ids=r=>r.map(x=>x.modelId);
test("recall column high first, toggle reverses, missing last",()=>{
 const first=nextHeatmapSort(null,"healthcare","recall");
 assert.deepEqual(first,{column:"healthcare",direction:"desc"});
 assert.deepEqual(ids(sortExecutiveRows(rows,first,"recall")),["Qwen9","Qwen4","Nemotron4","Other"]);
 assert.deepEqual(ids(sortExecutiveRows(rows,nextHeatmapSort(first,"healthcare","recall"),"recall")),["Nemotron4","Qwen4","Qwen9","Other"]);
});
test("false positives smaller first and missing always last",()=>{
 const sort=nextHeatmapSort(null,"healthcare","fp");
 assert.equal(sort.direction,"asc");
 assert.deepEqual(ids(sortExecutiveRows(rows,sort,"fp")),["Nemotron4","Qwen4","Qwen9","Other"]);
});
test("switching columns resets sort and names are alphabetical",()=>{
 assert.deepEqual(nextHeatmapSort({column:"model",direction:"desc"},"healthcare","fp"),{column:"healthcare",direction:"asc"});
 assert.deepEqual(ids(sortExecutiveRows(rows,{column:"model",direction:"asc"},"recall")),["Nemotron4","Other","Qwen4","Qwen9"]);
});
test("tie breaks consistently; input unchanged",()=>{
 const a=[{modelId:"b",cells:{healthcare:{totalGold:1,positiveRecall:.5}}},{modelId:"a",cells:{healthcare:{totalGold:1,positiveRecall:.5}}}];
 assert.deepEqual(ids(sortExecutiveRows(a,{column:"healthcare",direction:"desc"},"recall")),["a","b"]);
 assert.deepEqual(ids(a),["b","a"]);
});
