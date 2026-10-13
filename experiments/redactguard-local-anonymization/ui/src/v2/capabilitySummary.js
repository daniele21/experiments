// Aggregated capability evidence only: no source document or PII values.
export const CAPABILITY_DEFS = [
  { id:"realistic", title:"Documenti realistici", subtitle:"Formati ed entità comuni", rank:0 },
  { id:"challenge", title:"Semantic challenge", subtitle:"Categorie PII e casi contrastivi", rank:1 },
  { id:"healthcare", title:"Healthcare", subtitle:"Diagnosi, trattamenti, esami e dati clinici", rank:2 },
  { id:"ambiguous", title:"PII ambigue", subtitle:"Dipendenza dal contesto in quattro settori", rank:3 },
];

export function capabilityFromDataset(datasetId) {
  const id=String(datasetId??"").toLowerCase();
  if(id.includes("healthcare_synthetic") || id.includes("hc-synthetic")) return "healthcare";
  if(id.includes("ambiguous_synthetic") || id.includes("amb-synthetic")) return "ambiguous";
  if(id.includes("challenge")) return "challenge";
  if(id.includes("realistic")) return "realistic";
  return null;
}
function numeric(v) { return typeof v==="number" && Number.isFinite(v) ? v : null; }
function scalar(...v){return v.find(x=>numeric(x)!==null)??null;}
const safeRatio=(a,b)=>b>0 ? a/b : null;

export function summarizeModelCapability(id,aggregate) {
 const byDoc=Object.values(aggregate?.by_document??{});
 const positive=byDoc.filter(d=>(d.gold_count??0)>0);
 const negative=byDoc.filter(d=>d.gold_count===0);
 const validPos=positive.filter(d=>d.quality_available!==false && (d.inference_failures??0)===0);
 const validNeg=negative.filter(d=>d.quality_available!==false && (d.inference_failures??0)===0);
 // System recall weights all gold entities, including failed cases as leaked.
 const totalGold=positive.reduce((n,d)=>n+(d.gold_count??0),0);
 const tp=validPos.reduce((n,d)=>n+(d.system_tp??d.tp??0),0);
 const negativeFpCases=validNeg.filter(d=>(d.system_fp??d.fp??0)>0).length;
 const byType=Object.entries(aggregate?.by_type??{})
   .filter(([,v])=>(v?.gold_count??0)>0)
   .map(([type,v])=>({type,gold:v.gold_count,recall:scalar(v.pii_recall),fn:v.fn??null}))
   .sort((a,b)=>a.recall===null?1:b.recall===null?-1:a.recall-b.recall || a.type.localeCompare(b.type));
 const macro=aggregate?.macro_family??aggregate?.macro??{};
 return {
  modelId:id, documents:byDoc.length,
  validDocuments:byDoc.filter(d=>d.quality_available!==false && (d.inference_failures??0)===0).length,
  positiveCases:positive.length, negativeCases:negative.length,
  positiveRecall:safeRatio(tp,totalGold),
  balancedRecall:scalar(macro.system_pii_recall,macro.pii_recall),
  negativeFalsePositiveRate:safeRatio(negativeFpCases,validNeg.length),
  negativeValidated:validNeg.length,
  negativeFalsePositiveCases:negativeFpCases,
  incompleteNegatives:negative.length-validNeg.length,
  totalGold, tp, types:byType,
  reviewedCases:byDoc.filter(d=>d.human_reviewed===true).length,
 };
}

export function summarizeCapabilitySuite({key,suiteId,datasetId,createdAt,models},metrics) {
 const category=capabilityFromDataset(datasetId);
 if(!category||!metrics||typeof metrics!=="object")return null;
 return {
  category, runKey:key, suiteId, datasetId, createdAt,
  models:Object.entries(metrics).map(([id,m])=>summarizeModelCapability(id,m)),
 };
}
// The latest SUITE is not necessarily the latest result for every MODEL.
// Build one capability view from the newest available measurement of each
// model in the same exact dataset version, keeping the underlying run provenance.
export function selectLatestCapabilityRuns(runs) {
 const out = {};
 const sorted = [...runs].filter(Boolean).sort((a,b) =>
   (Date.parse(b.createdAt??"")||0)-(Date.parse(a.createdAt??"")||0) ||
   String(b.runKey??"").localeCompare(String(a.runKey??"")));
 for (const item of sorted) {
   if (!item.category || !item.datasetId || !Array.isArray(item.models)) continue;
   if (!out[item.category]) {
     out[item.category] = {
       ...item, models: [], mergedRunCount: 0,
       excludedDatasetVersions: new Set(), referenceRunKey: item.runKey,
     };
   }
   const group=out[item.category];
   if (item.datasetId !== group.datasetId) {
     group.excludedDatasetVersions.add(item.datasetId);
     continue;
   }
   let added=false;
   for (const model of item.models) {
     if (!model?.modelId || group.models.some(m=>m.modelId===model.modelId)) continue;
     // Not all older suites have a stored content fingerprint. That is an
     // unknown verification status, not proof of equality.
     const checks=[
       [item.evaluationSchema,group.evaluationSchema],
       [item.contractSnapshot,group.contractSnapshot],
       [model.inputFingerprint,group.models[0]?.inputFingerprint],
     ];
     const mismatch=checks.some(([x,y])=>x!=null && y!=null && x!==y);
     const unverified=checks.some(([x,y])=>x==null || y==null);
     group.models.push({
       ...model,
       runKey:item.runKey,
       suiteId:item.suiteId,
       createdAt:item.createdAt,
       contractSnapshot:item.contractSnapshot??null,
       inputFingerprint:model.inputFingerprint??null,
       comparability:mismatch?"different_protocol":unverified?"unverified":"verified",
     });
     added=true;
   }
   if (added) group.mergedRunCount++;
 }
 for (const group of Object.values(out)) {
   group.excludedDatasetVersions=[...group.excludedDatasetVersions];
   group.models.sort((a,b)=>a.modelId.localeCompare(b.modelId));
 }
 return out;
}
