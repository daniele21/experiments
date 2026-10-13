import { useEffect, useMemo, useState } from "react";
import { CAPABILITY_DEFS, selectLatestCapabilityRuns } from "./capabilitySummary";
import { privacyFrontier, summarizeExecutive, percentage } from "./executiveAnalytics";
import { shortModel } from "./evidence";
import ExecutiveParetoChart, { modelColor } from "./ExecutiveParetoChart";
import ExecutiveDatasetHeatmap from "./ExecutiveDatasetHeatmap";
import "./executive-dashboard.css";

const dateOf=value=>{
 const parsed=Date.parse(value??"");
 return Number.isFinite(parsed)?new Date(parsed).toLocaleDateString("it-IT"):"Data non indicata";
};
const readableType=x=>String(x??"").replaceAll("_"," ");
const canReport=(report)=>Boolean(report?.models?.length);
const displayNumber=n=>typeof n==="number"&&Number.isFinite(n)?n.toLocaleString("it-IT"):"—";

function Insight({kind,label,heading,detail,onClick}) {
 return <article className="rb3-insight">
   <div className="rb3-insight-icon" aria-hidden="true">{kind}</div>
   <div><span className="rb3-insight-label">{label}</span><h3>{heading}</h3><p>{detail}</p></div>
   {onClick&&<button type="button" onClick={onClick}>Apri evidenze ↗</button>}
 </article>;
}

export default function ExecutiveDashboard({onOpenRun,onOpenCapabilities}) {
 const [items,setItems]=useState([]);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState(null);
 const [refresh,setRefresh]=useState(0);
 const [category,setCategory]=useState("healthcare");
 const [mode,setMode]=useState("privacy");
 const [selected,setSelected]=useState(null);
 const [showModelFilter,setShowModelFilter]=useState(false);
 useEffect(()=>{
  const controller=new AbortController();
  setLoading(true);
  fetch("/api/capabilities",{signal:controller.signal})
   .then(response=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();})
   .then(data=>{setItems(Array.isArray(data?.capabilities)?data.capabilities:[]);setError(null);})
   .catch(e=>{if(e.name!=="AbortError")setError(e.message??String(e));})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
  return ()=>controller.abort();
 },[refresh]);
 const latest=useMemo(()=>selectLatestCapabilityRuns(items),[items]);
 const allModelIds=useMemo(()=>[...new Set(Object.values(latest).flatMap(report=>
   (report.models??[]).map(m=>m.modelId)))].sort((a,b)=>a.localeCompare(b,"en",{numeric:true})),[latest]);
 const chosenIds=useMemo(()=>selected===null?allModelIds:
   allModelIds.filter(id=>selected.includes(id)),[allModelIds,selected]);
 const chosenSet=useMemo(()=>new Set(chosenIds),[chosenIds]);
 const report=latest[category]??null;
 const visibleModels=(report?.models??[]).filter(m=>chosenSet.has(m.modelId));
 const analytics=useMemo(()=>summarizeExecutive(latest,category,chosenIds,mode),[latest,category,chosenIds,mode]);
 const frontier=analytics.frontier;
 const firstInvalid=visibleModels.filter(m=>m.documents>0&&m.validDocuments<m.documents)
  .sort((a,b)=>(a.validDocuments/a.documents)-(b.validDocuments/b.documents))[0]??null;
 const mostMissed=analytics.worstTypes[0]??null;
 const maxFrontier=frontier.frontier.length;
 const filterCount=chosenIds.length;
 function toggleModel(id) {
  const next=new Set(chosenIds);
  if(next.has(id))next.delete(id);else next.add(id);
  setSelected([...next]);
 }
 const openModel=(modelId,runKey)=>{
  const m=(latest[category]?.models??[]).find(m=>m.modelId===modelId);
  onOpenRun(runKey??m?.runKey,modelId);
 };
 return <section className="rb3-executive">
  <div className="rb3-page-head">
   <div><span className="rb2-kicker">REDACTBENCH / EXECUTIVE INTELLIGENCE</span>
    <h1>Model intelligence</h1>
    <p>Quali modelli proteggono meglio i dati, con quale compromesso e dove falliscono?</p>
   </div>
   <button className="rb3-action-ghost" type="button" onClick={()=>setRefresh(x=>x+1)}
    disabled={loading}>{loading?"Aggiornamento…":"↻ Aggiorna"}</button>
  </div>
  {error&&<div className="rb3-warning" role="alert">Impossibile leggere i risultati: {error}</div>}
  <div className="rb3-hero-controls">
    <div className="rb3-field"><label htmlFor="rb3-dataset">Benchmark</label>
     <select id="rb3-dataset" value={category} onChange={e=>setCategory(e.target.value)}>
      {CAPABILITY_DEFS.map(d=><option key={d.id} value={d.id}>{d.title}{latest[d.id]?"":" · non testato"}</option>)}
     </select>
    </div>
    <div className="rb3-mode-switch" role="group" aria-label="Tipologia di Pareto frontier">
     <button type="button" className={mode==="privacy"?"active":""} aria-pressed={mode==="privacy"}
      onClick={()=>setMode("privacy")}>◈ Privacy Frontier</button>
     <button type="button" className={mode==="efficiency"?"active":""} aria-pressed={mode==="efficiency"}
      onClick={()=>setMode("efficiency")}>↗ Efficiency Frontier</button>
    </div>
    <button className={showModelFilter?"rb3-action-ghost rb3-action-ghost--active":"rb3-action-ghost"}
      type="button" aria-expanded={showModelFilter} onClick={()=>setShowModelFilter(v=>!v)}>
       Modelli · {filterCount}/{allModelIds.length} <span aria-hidden="true">{showModelFilter?"▴":"▾"}</span>
    </button>
  </div>
  {showModelFilter&&<div className="rb3-model-filter" aria-label="Modelli selezionati">
    <div className="rb3-model-filter__actions"><span>Seleziona i modelli nei grafici</span>
     <button type="button" onClick={()=>setSelected(null)}>Tutti</button>
     <button type="button" onClick={()=>setSelected([])}>Nessuno</button>
    </div>
    <div className="rb3-model-filter__chips">
     {allModelIds.map(id=><label key={id} className="rb3-model-chip">
       <input type="checkbox" checked={chosenSet.has(id)} onChange={()=>toggleModel(id)}/>
       <i style={{backgroundColor:modelColor(id,allModelIds)}}/>
       <span>{shortModel(id)}</span>
     </label>)}
    </div>
   </div>}
  {!loading && !canReport(report) ? <div className="rb3-empty">
    <h2>Nessun risultato disponibile per questo benchmark</h2>
    <p>Esegui almeno una suite locale. La dashboard non genera punteggi dimostrativi o classifiche inventate.</p>
    <button className="rb3-action-primary" type="button" onClick={onOpenCapabilities}>Apri benchmark per capacità →</button>
   </div> : <>
  <div className="rb3-metadata">
    <span><strong>{visibleModels.length}</strong> modelli selezionati</span>
    <span><strong>{report?.mergedRunCount??0}</strong> suite sorgenti</span>
    <span>Gold <strong>{report?.datasetId??"n/d"}</strong></span>
    <span>{loading?"Caricamento…":`Aggiornato ${dateOf(report?.createdAt)}`}</span>
  </div>
  <div className="rb3-hero-grid">
    <section className="rb3-panel rb3-primary-panel">
      <div className="rb3-panel-heading">
       <div><span className="rb2-kicker">LA DECISIONE / FRONTIERA PARETO</span>
        <h2>{mode==="privacy"?"Qualità vs sovra-anonimizzazione":"Qualità vs velocità"}</h2></div>
       <span className="rb3-pane-counter">{maxFrontier} non dominati</span>
      </div>
      <ExecutiveParetoChart frontier={frontier} mode={mode} modelIds={allModelIds}
         onOpenModel={openModel}/>
      <p className="rb3-frontier-disclaimer">{analytics.advisory}
       {frontier.excluded>0&&` ${frontier.excluded} modello/i esclusi per dati mancanti o protocollo incompatibile.`}
       {mode==="efficiency"&&frontier.valid&&` Suite: ${frontier.provenance}. Latenza p50 su campioni dedicati: non è il tempo per completare l'intero dataset.`}</p>
    </section>
    <aside className="rb3-insight-column" aria-label="Insight decisionali">
      <div className="rb3-insights-head"><span className="rb2-kicker">COSA DICONO I DATI</span>
       <h2>Key insights</h2></div>
      {analytics.bestRecall ?
       <Insight kind="↑" label="Massimo riconoscimento"
         heading={shortModel(analytics.bestRecall.modelId)}
         detail={`${percentage(analytics.bestRecall.positiveRecall)} delle PII gold riconosciute sui casi positivi; ${analytics.bestRecall.totalGold} PII in questo benchmark.`}
         onClick={()=>openModel(analytics.bestRecall.modelId,analytics.bestRecall.runKey)}/>:
       <Insight kind="—" label="Riconoscimento" heading="Dati insufficienti"
        detail="Nessuna misura di recall valida nei modelli selezionati."/>}
      {analytics.leastOverredaction ?
       <Insight kind="◎" label="Minore sovra-anonimizzazione"
         heading={shortModel(analytics.leastOverredaction.modelId)}
         detail={`${percentage(analytics.leastOverredaction.negativeFalsePositiveRate)} casi negativi con falsi positivi (${analytics.leastOverredaction.negativeValidated} negativi validi).`}
         onClick={()=>openModel(analytics.leastOverredaction.modelId,analytics.leastOverredaction.runKey)}/>:
       <Insight kind="—" label="Sovra-anonimizzazione" heading="Non misurata"
         detail="Servono casi negativi validi per valutare i falsi positivi."/>}
      {firstInvalid ?
       <Insight kind="!" label="Affidabilità da migliorare"
         heading={shortModel(firstInvalid.modelId)}
         detail={`${firstInvalid.documents-firstInvalid.validDocuments} di ${firstInvalid.documents} inferenze non valide. Il recall può includere fallimenti nel denominatore.`}
         onClick={()=>openModel(firstInvalid.modelId,firstInvalid.runKey)}/>:
       <Insight kind="✓" label="Validità delle inferenze"
         heading={visibleModels.length?"Tutti i casi elaborati":"Nessun modello selezionato"}
         detail={visibleModels.length?"Nessuna inferenza fallita nei modelli selezionati con dati disponibili.":"Seleziona almeno un modello."}/>}
    </aside>
  </div>
  <ExecutiveDatasetHeatmap latest={latest} modelFilter={chosenSet} onOpenRun={onOpenRun}/>
  <div className="rb3-secondary-grid">
   <section className="rb3-panel rb3-risk-panel">
    <div className="rb3-section-head"><div><span className="rb2-kicker">DOVE SI PERDE PROTEZIONE</span>
     <h2>PII più difficili</h2><p>Le categorie con minor recall, per modello, nel dataset selezionato.</p></div></div>
    <div className="rb3-type-list">
     {analytics.worstTypes.length?analytics.worstTypes.slice(0,6).map((t,i)=><div key={`${t.modelId}:${t.type}:${i}`} className="rb3-type-row">
       <div><strong>{readableType(t.type)}</strong><span>{shortModel(t.modelId)} · {displayNumber(t.gold)} gold</span></div>
       <span className="rb3-type-value">{percentage(t.recall)}</span>
       <div className="rb3-type-track"><i style={{width:`${t.recall*100}%`}}/></div>
     </div>):<div className="rb3-empty-inline">Nessuna metrica per categoria disponibile.</div>}
    </div>
   </section>
   <section className="rb3-panel rb3-reliability">
    <div className="rb3-section-head"><div><span className="rb2-kicker">QUALITÀ DELL'EVIDENZA</span>
     <h2>Affidabilità del test</h2><p>Campioni validi e provenienza dei risultati.</p></div></div>
    {visibleModels.length?visibleModels.map(m=><button type="button" className="rb3-reliability-row"
       key={m.modelId} onClick={()=>openModel(m.modelId,m.runKey)}>
      <div><strong>{shortModel(m.modelId)}</strong>
        <span>{displayNumber(m.validDocuments)} / {displayNumber(m.documents)} casi validi</span></div>
      <span className="rb3-reliability-pct">{m.documents?percentage(m.validDocuments/m.documents):"—"}</span>
      <i aria-hidden="true"><b style={{width:m.documents?`${m.validDocuments/m.documents*100}%`:"0%"}}/></i>
    </button>):<p className="rb3-empty-inline">Nessun modello selezionato.</p>}
    <p className="rb3-micro">I confronti tra suite dipendono dalla versione del gold, dalla configurazione e dal protocollo. Gold revisionato manualmente: {analytics.goldReviewed?"sì per questi casi":"non verificato o non completo"}.</p>
   </section>
  </div>
  </>}
 </section>;
}
