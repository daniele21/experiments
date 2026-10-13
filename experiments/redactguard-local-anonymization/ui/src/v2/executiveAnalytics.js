/**
 * Executive decision evidence for RedactBench.
 *
 * A Pareto point is eligible only if it is on the same exact dataset version,
 * has both axes observed, and hasn't been proven to use a different contract.
 * Mixed-protocol measurements remain visible as excluded evidence, never as
 * proof that a model dominates another model.
 */
export const valid = x => typeof x==="number" && Number.isFinite(x) && x>=0;
export const percentage = x => valid(x) ? `${(100*x).toFixed(1)}%` : "—";

export function nonDominated(points, xKey, yKey, {lowerX=true,higherY=true}={}) {
 const usable=points.filter(p=>valid(p?.[xKey])&&valid(p?.[yKey]));
 return usable.filter(a=>!usable.some(b=>{
   if (a === b) return false;
   const xBetter=lowerX ? b[xKey]<=a[xKey] : b[xKey]>=a[xKey];
   const yBetter=higherY ? b[yKey]>=a[yKey] : b[yKey]<=a[yKey];
   const strict= b[xKey]!==a[xKey] || b[yKey]!==a[yKey];
   return xBetter && yBetter && strict;
 }));
}

export function privacyFrontier(report, selectedModels) {
 const filter = new Set(selectedModels);
 const points=(report?.models??[]).filter(m=>filter.has(m.modelId)).map(m=>({
  modelId:m.modelId,runKey:m.runKey,suiteId:m.suiteId,
  x:m.negativeValidated>0 ? m.negativeFalsePositiveRate : null,
  y:m.totalGold>0 ? m.positiveRecall : null,
  comparability:m.comparability,
  validCases:m.validDocuments, cases:m.documents,
  negatives:m.negativeValidated, totalGold:m.totalGold,
 })).map(p=>({...p,eligible:valid(p.x)&&valid(p.y)&&p.comparability!=="different_protocol"}));
 const good=points.filter(p=>p.eligible);
 const frontier=nonDominated(good,"x","y");
 const onFrontier=new Set(frontier.map(p=>p.modelId));
 const results=points.map(p=>({...p,frontier:p.eligible&&onFrontier.has(p.modelId),
   dominated:p.eligible&&!onFrontier.has(p.modelId)}));
 const provisional=good.some(p=>p.comparability!=="verified" && p.comparability!=="reference");
 return {points:results,frontier:frontier.sort((a,b)=>a.x-b.x||a.y-b.y),
   eligible:good.length,excluded:points.length-good.length,provisional};
}

export function efficiencyFrontier(report, selectedModels) {
 const filter=new Set(selectedModels);
 const chosen=(report?.models??[]).filter(m=>filter.has(m.modelId));
 const suiteGroups=new Map();
 for(const m of chosen){
  if(!m.latencyVerified || !valid(m.p50Ms) || m.p50Ms<=0 ||
     !valid(m.positiveRecall) || !m.latencyProtocol)continue;
  const key=JSON.stringify([m.suiteId,m.latencyProtocol]);
  if(!suiteGroups.has(key))suiteGroups.set(key,[]);
  suiteGroups.get(key).push(m);
 }
 // Never join Qwen's speed measured on one set of prompts with a different
 // Nemotron suite. Choose the largest controlled cohort.
 const cohorts=[...suiteGroups.values()].sort((a,b)=>b.length-a.length||
   (Date.parse(b[0]?.createdAt??"")||0)-(Date.parse(a[0]?.createdAt??"")||0));
 const group=cohorts[0]??[];
 const points=group.map(m=>({
  modelId:m.modelId,runKey:m.runKey,suiteId:m.suiteId,
  x:m.p50Ms,y:m.positiveRecall,latencySamples:m.latencySamples,
  latencyProtocol:m.latencyProtocol,comparability:m.comparability,eligible:true,
 }));
 const frontier=nonDominated(points,"x","y").sort((a,b)=>a.x-b.x||a.y-b.y);
 const onFrontier=new Set(frontier.map(p=>p.modelId));
 return {
   points:points.map(p=>({...p,frontier:onFrontier.has(p.modelId),
     dominated:!onFrontier.has(p.modelId)})),
   frontier,eligible:points.length,excluded:chosen.length-points.length,
   valid:points.length>=2,
   provenance:group[0]?.suiteId??null,
 };
}

export function summarizeExecutive(latest, category, selectedModels, mode) {
 const report=latest?.[category]??null;
 const chosen=(report?.models??[]).filter(m=>selectedModels.includes(m.modelId));
 // A known contract mismatch must not become an executive "winner".
 const comparable=chosen.filter(m=>m.comparability!=="different_protocol");
 const frontier=mode==="efficiency"?
   efficiencyFrontier(report,selectedModels):privacyFrontier(report,selectedModels);
 const withRecall=comparable.filter(m=>valid(m.positiveRecall)&&m.totalGold>0);
 const withNegative=comparable.filter(m=>valid(m.negativeFalsePositiveRate)&&m.negativeValidated>0);
 const bestRecall=[...withRecall].sort((a,b)=>b.positiveRecall-a.positiveRecall)[0]??null;
 const leastOverredaction=[...withNegative].sort((a,b)=>a.negativeFalsePositiveRate-b.negativeFalsePositiveRate)[0]??null;
 const worstTypes=comparable.flatMap(m=>(m.types??[]).filter(t=>valid(t.recall)&&t.gold>0)
    .map(t=>({modelId:m.modelId,type:t.type,recall:t.recall,gold:t.gold})))
    .sort((a,b)=>a.recall-b.recall||b.gold-a.gold).slice(0,8);
 const reliable=chosen.filter(m=>m.documents>0&&m.validDocuments===m.documents);
 return {report,chosen,frontier,bestRecall,leastOverredaction,worstTypes,
  fullyValid:reliable.length,selectedCount:chosen.length,
  goldReviewed:chosen.every(m=>m.reviewedCases===m.documents&&m.documents>0),
  advisory:mode==="efficiency" && !frontier.valid
   ?"Servono almeno due modelli con latenza senza cache misurata nella stessa suite."
   :frontier.eligible<2
    ?"I dati disponibili non bastano per stabilire una frontiera significativa."
    :frontier.provisional
     ?"La frontiera è esplorativa: alcune verifiche del protocollo dei run mancano."
     :"La frontiera mostra compromessi non dominati, non una certificazione di sicurezza.",
 };
}
