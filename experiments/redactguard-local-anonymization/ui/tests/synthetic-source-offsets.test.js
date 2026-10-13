import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { spanMatchesText } from "../src/v2/evidence.js";
import { resolveBundledDatasetSource, indexBenchmarkTexts } from "../src/v2/datasetText.js";

const dirname=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(dirname,"../..");
const ids=["amb10-pos","amb14-pos"];
const datasets=["ambiguous_synthetic_v0.1","healthcare_synthetic_v0.1"];

test("all committed synthetic positive gold values align with exact canonical text",()=>{
 for(const dataset of datasets){
  const source=resolveBundledDatasetSource(dataset);
  const rows=readFileSync(path.join(root,source),"utf8").trim().split("\n").map(JSON.parse);
  const indexed=indexBenchmarkTexts(rows);
  assert.equal(rows.length,48);
  for(const row of rows){
   assert.equal(indexed.get(row.id),row.text);
   for(const entity of row.entities){
    const start=row.text.indexOf(entity.value);
    assert.ok(start>=0,`${row.id}: gold missing ${entity.pii_type}`);
    assert.equal(spanMatchesText(row.text,{
     start,end:start+entity.value.length,value:entity.value,
    }),true,`${row.id}: source offset contract invalid`);
   }
  }
 }
});

test("amb14-pos and amb10-pos source spans match gold without needing re-inference",()=>{
 const source=resolveBundledDatasetSource("ambiguous_synthetic_v0.1");
 const rows=readFileSync(path.join(root,source),"utf8").trim().split("\n").map(JSON.parse);
 for(const id of ids){
  const row=rows.find(x=>x.id===id);
  assert.ok(row,id);
  const value=row.entities[0].value;
  const start=row.text.indexOf(value);
  assert.equal(spanMatchesText(row.text,{...row.entities[0],start,end:start+value.length}),true);
  assert.equal(createHash("sha256").update(row.text).digest("hex").length,64);
  if(id==="amb14-pos")assert.equal(start,51);
 }
});
