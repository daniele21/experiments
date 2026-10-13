import { useEffect, useMemo, useState } from "react";
import { CAPABILITY_DEFS, selectLatestCapabilityRuns } from "./capabilitySummary";
import { shortModel } from "./evidence";
import "./capabilities.css";

const fmt = x => x === null || x === undefined ? "—" : `${(x * 100).toFixed(1)}%`;
const positiveBar = x => x===null||x===undefined?0:Math.max(0,Math.min(100,x*100));
const dateLabel = value => {
 const date=Date.parse(value??"");
 return Number.isFinite(date) ? new Date(date).toLocaleDateString("it-IT",{day:"2-digit",month:"short",year:"numeric"}) : "Data non disponibile";
};
const confidenceLabel = value =>
 value==="reference"?"Run di riferimento":
 value==="different_protocol"?"Configurazione diversa":
 value==="unverified"?"Comparabilità non verificata":"Stesso dataset e protocollo verificati";
function StatLine({label,value,good=false}){
 return <div className="rb2-cap-stat"><span>{label}</span><strong className={good?"rb2-cap-positive":""}>{value}</strong></div>;
}
export default function CapabilityBenchmark({onOpenRun}){
 const [items,setItems]=useState([]);
 const [selected,setSelected]=useState("healthcare");
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState(null);
 const [reload,setReload]=useState(0);
 useEffect(()=>{
   const controller=new AbortController();
   setLoading(true);
   fetch("/api/capabilities",{signal:controller.signal})
    .then(resp=>{if(!resp.ok)throw Error(`HTTP ${resp.status}`);return resp.json()})
    .then(data=>{setItems(Array.isArray(data?.capabilities)?data.capabilities:[]);setError(null);})
    .catch(e=>{if(e.name!=="AbortError")setError(String(e.message||e));})
    .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
   return ()=>controller.abort();
 },[reload]);
 const latest=useMemo(()=>selectLatestCapabilityRuns(items),[items]);
 const active=latest[selected]??null;
 const definition=CAPABILITY_DEFS.find(x=>x.id===selected);
 const command=selected==="realistic"?"config/suite.yaml":
   selected==="challenge"?"config/suite-challenge.yaml":`config/suite-${selected}.yaml`;
 return <section className="rb2-capabilities">
  <div className="rb2-page-heading"><div><span className="rb2-kicker">PANORAMICA / CAPACITÀ</span><h1>Capability benchmark</h1><p>Quanto bene i modelli distinguono dati da proteggere e informazioni innocue?</p></div>
   <button className="rb2-cap-refresh" type="button" onClick={()=>setReload(x=>x+1)}>↻ Aggiorna</button></div>
  {loading&&<div className="rb2-cap-note">Caricamento delle suite locali…</div>}
  {error&&<div role="alert" className="rb2-cap-error">Impossibile leggere le suite: {error}</div>}
  <div className="rb2-cap-picker" role="tablist" aria-label="Area del benchmark">
   {CAPABILITY_DEFS.map(cap=>{
     const report=latest[cap.id];
     return <button key={cap.id} type="button" role="tab" aria-selected={selected===cap.id}
      className={selected===cap.id?"active":""} onClick={()=>setSelected(cap.id)}>
       <strong>{cap.title}</strong><small>{report ? `${report.models.length} modelli · ${report.models[0]?.documents??0} casi` : "Non ancora testato"}</small>
     </button>;
   })}
  </div>
  <div className="rb2-cap-context">
   <div><span className="rb2-kicker">CAPACITÀ SELEZIONATA</span><h2>{definition?.title}</h2><p>{definition?.subtitle}</p></div>
   {active&&<button className="rb2-cap-open" type="button" onClick={()=>onOpenRun(active.runKey)}>Apri ultima suite →</button>}
  </div>
  {!active ? <div className="rb2-cap-empty"><h3>Ancora nessun benchmark completato</h3>
    <p>Esegui i test sul Mac, poi torna qui. Non viene inventato alcun punteggio in assenza dei risultati.</p>
    <code>uv run redact-bench suite --config {command} --no-ensure-models</code>
   </div> : <>
   <div className="rb2-cap-runline">
     <strong>{active.models.length} modelli</strong> · <strong>{active.mergedRunCount} suite</strong> · Dataset {active.datasetId}
     {active.mergedRunCount>1&&<span className="rb2-cap-run-note"> Confronto multi-run: per ogni modello viene scelto il risultato più recente.</span>}
     {active.excludedDatasetVersions.length>0&&<span className="rb2-cap-run-note"> {active.excludedDatasetVersions.length} versioni diverse del dataset escluse per non mescolare il gold.</span>}
   </div>
   <div className="rb2-cap-modelgrid">
    {active.models.map(m=><article className="rb2-cap-model" key={m.modelId}>
      <h3>{shortModel(m.modelId)}</h3>
      <div className="rb2-cap-provenance"><span>{dateLabel(m.createdAt)}</span><span title={m.suiteId}>{m.suiteId??"Run"}</span></div>
      <span className={`rb2-cap-confidence ${m.comparability==="different_protocol"?"rb2-cap-confidence--warning":""}`}
        title="Confronto tra run: versione dataset, schema, configurazione e fingerprint dei casi">
        {confidenceLabel(m.comparability)}
      </span>
      <div className="rb2-cap-hero"><strong>{fmt(m.positiveRecall)}</strong><span>Recall sui casi positivi</span></div>
      <div className="rb2-cap-meter" role="progressbar" aria-label={`Recall positivo ${m.modelId}`} aria-valuenow={positiveBar(m.positiveRecall)} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${positiveBar(m.positiveRecall)}%`}}/></div>
      <StatLine label="Negativi con falsi positivi" value={fmt(m.negativeFalsePositiveRate)}/>
      <StatLine label="Negativi validi" value={`${m.negativeValidated} / ${m.negativeCases}`}/>
      <StatLine label="Documenti validi" value={`${m.validDocuments} / ${m.documents}`}/>
      <p className="rb2-cap-model-note">Per i negativi, più basso è meglio. I casi falliti non sono conteggiati come verifiche riuscite.</p>
      <button type="button" className="rb2-cap-open rb2-cap-card-action"
        onClick={()=>onOpenRun(m.runKey,m.modelId)} aria-label={`Apri evidenze di ${shortModel(m.modelId)}`}>Esplora i risultati →</button>
     </article>)}
   </div>
   <div className="rb2-cap-breakdowns"><div className="rb2-cap-breakdowns__heading"><h3>Quali PII risultano difficili?</h3><span>Recall per categoria · tipi con gold positivo</span></div>
     <div className="rb2-cap-breakdown-grid">
     {active.models.map(m=><div key={m.modelId} className="rb2-cap-breakdown"><strong>{shortModel(m.modelId)}</strong>
      {m.types.length? m.types.map(t=><div key={t.type} className="rb2-cap-type"><div><span>{t.type.replaceAll("_"," ")}</span><span>{fmt(t.recall)} · {t.gold} gold</span></div><div className="rb2-cap-meter"><span style={{width:`${positiveBar(t.recall)}%`}}/></div></div>):
      <p className="rb2-cap-model-note">Nessuna distribuzione per tipo disponibile.</p>}
     </div>)}
     </div>
   </div>
   <p className="rb2-cap-note">I risultati sono selezionati singolarmente per modello all'interno della stessa versione del dataset. Se la configurazione o gli input differiscono, i punteggi non costituiscono un confronto controllato. Gold non necessariamente revisionato; nessuna certificazione privacy. Le quattro capacità rimangono benchmark separati.</p>
  </>}
 </section>;
}
