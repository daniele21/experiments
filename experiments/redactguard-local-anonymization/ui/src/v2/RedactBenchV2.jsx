import { useEffect, useMemo, useState } from "react";
import ThemeToggle from "../components/ThemeToggle";
import { appRoutes } from "../routing";
import { modelsIn, shortModel } from "./evidence";
import ModelComparison from "./ModelComparison";
import DocumentComparison from "./DocumentComparison";
import DocumentWorkspace from "./DocumentWorkspace";
import "./base.css";

export default function RedactBenchV2({
 detail,route,runs,selectedKey,onSelectRun,selectedModel,onSelectModel,onRefresh,
}){
 const available=useMemo(()=>modelsIn(detail),[detail]);
 const modelA=available.includes(selectedModel)?selectedModel:available[0]??null;
 const [otherModel,setOtherModel]=useState(null);
 const modelB=available.find(m=>m===otherModel&&m!==modelA)??available.find(m=>m!==modelA);
 const selectedModels=[modelA,modelB].filter(Boolean);
 const page=route.page;
 const openDoc=(doc,model=modelA)=>{
  if(!model)return;
  onSelectModel?.(model);
  route.navigate(appRoutes.clientDetail(doc,model));
 };
 useEffect(()=>{
  if(page==="detail"&&route.params?.model&&available.includes(route.params.model)&&route.params.model!==selectedModel){
   onSelectModel?.(route.params.model);
  }
 },[page,route.params?.model,available.join("|"),selectedModel,onSelectModel]);
 const date=detail?.summary?.createdAt ? new Date(detail.summary.createdAt).toLocaleDateString("it-IT",{day:"numeric",month:"short",year:"numeric"}):"Data sconosciuta";
 const status=detail?.summary?.status==="complete"?"Run completo":detail?.summary?.status==="incomplete"?"Run parziale":"Prove aggregate";
 const caption=detail?.summary?.source==="overview"?"Confronto tra run diversi — verifica comparabilità":`${available.length} modelli · ${date}`;
 const onDocuments=()=>route.navigate(appRoutes.clientDocuments);
 return <div className="rb2-root">
   <header className="rb2-topbar">
     <div className="rb2-run-context"><span className="rb2-kicker">BENCHMARK LOCALE / RISULTATI</span>
      <div className="rb2-run-title"><strong>{detail?.summary?.suiteId||detail?.summary?.runId||"Benchmark"}</strong><span className="rb2-run-indicator">{status}</span></div>
      <span className="rb2-run-subtitle">{caption}</span>
     </div>
     <div className="rb2-head-actions">
      <label>Run <select aria-label="Seleziona run" value={selectedKey} onChange={e=>onSelectRun(e.target.value)}>
       <option value="__overview__">Tutti i modelli (mixed evidence)</option>
       {runs.filter(x=>x.kind!=="latency").map(r=><option key={r.key} value={r.key}>{r.suiteId||r.runId} · {r.status}</option>)}
      </select></label>
      {available.length>1&&<label>Confronta <select aria-label="Modello A" value={modelA??""} onChange={e=>onSelectModel(e.target.value)}>{available.map(m=><option key={m} value={m}>{shortModel(m)}</option>)}</select></label>}
      {available.length>1&&<label>con <select aria-label="Modello B" value={modelB??""} onChange={e=>setOtherModel(e.target.value)}>{available.filter(m=>m!==modelA).map(m=><option key={m} value={m}>{shortModel(m)}</option>)}</select></label>}
      <ThemeToggle/>
      <button className="rb2-refresh" type="button" onClick={onRefresh} title="Aggiorna risultati">↻</button>
     </div>
   </header>
   <div className="rb2-content">
    {page==="models" ? <ModelComparison detail={detail} models={selectedModels} onOpenDocuments={onDocuments}/>:
     page==="documents" ? <DocumentComparison detail={detail} models={selectedModels} onOpenDocument={openDoc}/>:
     page==="detail" ? <DocumentWorkspace detail={detail} documentName={route.params.documentName} initialModel={route.params.model} models={[route.params.model,...selectedModels.filter(m=>m!==route.params.model)].filter(m=>available.includes(m)).slice(0,2)} onBack={onDocuments} onSelectModel={onSelectModel}/>:
     <ModelComparison detail={detail} models={selectedModels} onOpenDocuments={onDocuments}/>}
   </div>
   {page!=="detail"&&<footer className="rb2-legal-note">Dati elaborati localmente · Misure sperimentali su gold non necessariamente revisionato. Non costituiscono certificazione GDPR.</footer>}
 </div>;
}
