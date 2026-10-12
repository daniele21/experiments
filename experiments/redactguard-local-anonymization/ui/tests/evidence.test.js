import test from "node:test";
import assert from "node:assert/strict";
import {
  modelEvidence, documentEvidence, spansForModel, latencyVerified,
  compareInsight, spanMatchesText,
} from "../src/v2/evidence.js";

const qwenRun = {
  summary:{source:"suite",status:"complete",models:["four","nine"]},
  suiteMeta:{status:"completed",inference_cache_max_entries:0},
  latency:{manifest:{kind:"latency",models:["four","nine"],case_ids:["lettera.txt"],repeats_per_case:5}, metrics:{
    four:{micro:{latency_p50_ms:4056, latency_p95_ms:5190,cases:5}},
    nine:{micro:{latency_p50_ms:8667, latency_p95_ms:9900,cases:5}},
  }},
  metrics:{
    four:{micro:{cases:11,pii_recall:.9016, precision:.889,zero_leak_document_rate:6/11,system_fn:154,system_fp:176},
      macro_family:{system_pii_recall:.8625},
      by_document:{"lettera.txt":{gold_count:2,pii_recall:.5,system_fn:1,human_reviewed:false}}},
    nine:{micro:{cases:11,pii_recall:.8806,precision:.9187,zero_leak_document_rate:8/11},
      macro_family:{system_pii_recall:.9232},
      by_document:{"lettera.txt":{gold_count:2,pii_recall:1,human_reviewed:false}}},
  },
  docSpans:{"lettera.txt":{
    text:"Mario at Roma",
    gold:[{pii_type:"private_person",start:0,end:5,value:"Mario"},
          {pii_type:"private_address",start:9,end:13,value:"Roma"}],
    models:{
      four:{valid:true,missed:[{pii_type:"private_address",start:9,end:13,value:"Roma"}],redactions:[],overRedacted:[]},
      nine:{valid:true,missed:[],redactions:[],overRedacted:[]},
    },
  }},
};
test("verified same-suite cache-off latency",()=>{
  assert.equal(latencyVerified(qwenRun,"four"),true);
  assert.equal(modelEvidence(qwenRun,"four").p50,4056);
  assert.equal(modelEvidence(qwenRun,"nine").zeroCount,8);
  assert.equal(modelEvidence(qwenRun,"four").recall,.8625);
  assert.match(compareInsight(modelEvidence(qwenRun,"four"),modelEvidence(qwenRun,"nine"),"speed"),/2.1×/);
});
test("refuse legacy cached and mixed-source speed ranking",()=>{
  const old={...qwenRun,suiteMeta:{status:"completed",inference_cache_max_entries:256}};
  assert.equal(modelEvidence(old,"four").p50,null);
  assert.match(compareInsight(modelEvidence(old,"four"),modelEvidence(old,"nine"),"speed"),/non verificata/);
  const mixed={...qwenRun, summary:{...qwenRun.summary,source:"overview"}};
  assert.equal(modelEvidence(mixed,"four").cacheVerified,false);
});
test("document and offset evidence are consistent",()=>{
 const doc=documentEvidence(qwenRun,"lettera.txt",["four","nine"]);
 assert.equal(doc.metrics[0].fn,1);
 assert.equal(doc.metrics[1].recall,1);
 const spans=spansForModel(doc,"four");
 assert.equal(spans.invalidOffsets,0);
 assert.deepEqual(spans.items.map(x=>x.status),["detected","missed"]);
 assert.equal(spanMatchesText(doc.text,{start:0,end:5,value:"Other"}),false);
});
test("failed inference is unavailable, not zero recall",()=>{
 const broken=structuredClone(qwenRun);
 broken.docSpans["lettera.txt"].models.four.valid=false;
 assert.equal(documentEvidence(broken,"lettera.txt",["four"]).metrics[0].recall,null);
});
