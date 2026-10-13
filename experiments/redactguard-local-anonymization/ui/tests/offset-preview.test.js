import test from "node:test";
import assert from "node:assert/strict";
import { documentEvidence, spanMatchesText, spansForModel } from "../src/v2/evidence.js";

// Reproduces the 13 October amb10-pos symptom: valid canonical gold on both
// models, but one model-generated extra with an untrustworthy offset/value.
// Metrics (0% vs 100% recall) are independent of preview alignment.
const text = "La cartella del paziente contiene sedentarietà marcata nella valutazione individuale.";
const start = text.indexOf("sedentarietà marcata");
const end = start + "sedentarietà marcata".length;
const gold = {start,end,pii_type:"lifestyle_info",value:"sedentarietà marcata"};
const invalidExtra = {start:0,end:7,pii_type:"lifestyle_info",value:"sedentarietà marcata"};
const detail = {
  metrics:{
    qwen4:{by_document:{"amb10-pos":{gold_count:1,pii_recall:0,system_fn:1,quality_available:true}}},
    qwen9:{by_document:{"amb10-pos":{gold_count:1,pii_recall:1,system_tp:1,quality_available:true}}},
  },
  docSpans:{"amb10-pos":{
    text,
    gold:[gold],
    models:{
      qwen4:{valid:true,missed:[gold],overRedacted:[invalidExtra]},
      qwen9:{valid:true,missed:[],overRedacted:[invalidExtra]},
    },
  }},
};

test("an unalignable model extra does not hide a trusted missed gold PII",()=>{
  assert.equal(spanMatchesText(text,gold),true);
  const doc=documentEvidence(detail,"amb10-pos",["qwen4","qwen9"]);
  assert.equal(doc.metrics[0].recall,0);
  assert.equal(doc.metrics[1].recall,1);
  const missed=spansForModel(doc,"qwen4");
  assert.equal(missed.invalidGoldOffsets,0);
  assert.equal(missed.invalidExtraOffsets,1);
  assert.equal(missed.invalidOffsets,1);
  assert.deepEqual(missed.items.map(x=>x.status),["missed"]);
  assert.deepEqual([missed.items[0].start,missed.items[0].end],[start,end]);
  const found=spansForModel(doc,"qwen9");
  assert.equal(found.invalidGoldOffsets,0);
  assert.equal(found.invalidExtraOffsets,1);
  assert.deepEqual(found.items.map(x=>x.status),["detected"]);
});

test("a wrong GOLD offset still marks preview as unsafe to show",()=>{
  const doc=documentEvidence(detail,"amb10-pos",["qwen4","qwen9"]);
  doc.gold=[{...gold,start:start+1,end:end+1}];
  const evidence=spansForModel(doc,"qwen4");
  assert.equal(evidence.invalidGoldOffsets,1);
  assert.equal(evidence.items.length,0);
});

test("overlapping model extra never comes before matching gold span",()=>{
  const doc=documentEvidence(detail,"amb10-pos",["qwen4","qwen9"]);
  doc.metrics[0].raw.overRedacted=[{...gold,pii_type:"private_address"}];
  const evidence=spansForModel(doc,"qwen4");
  assert.equal(evidence.invalidExtraOffsets,0);
  assert.deepEqual(evidence.items.map(x=>x.status),["missed","extra"]);
});
