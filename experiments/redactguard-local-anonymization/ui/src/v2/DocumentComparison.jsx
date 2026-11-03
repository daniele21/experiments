import { useMemo, useState } from "react";
import {
  allDocuments,
  docPiiSummary,
  isNumber,
  modelsIn,
  piiTypeLabel,
  ratioText,
  shortModel,
} from "./evidence";
import "./documents.css";

const modeNames={recall:"Recall",leakage:"Leakage",fn:"PII mancate"};
function cellValue(item,mode){
 if(item?.status!=="ok")return item?.status==="failed"?"Run fallito":"Non disponibile";
 if(mode==="fn")return item.fn==null?"—":String(item.fn);
 return ratioText(item[mode]);
}
function colored(item,mode){
 if(item?.status!=="ok")return "unavailable";
 if(mode==="leakage"||mode==="fn")return (item[mode]??0)>0?"risk":"good";
 return isNumber(item.recall)?item.recall>=.95?"good":item.recall>=.8?"caution":"risk":"unavailable";
}
function DocMetric({item,mode,maxFn}){
 if(item?.status!=="ok")return <span className="rb2-doc-metric--unavailable">{cellValue(item,mode)}</span>;
 const v=item?.[mode];
 const width=mode==="fn" ? (maxFn?Math.max(0,(v??0)/maxFn*100):0) : isNumber(v)?Math.max(0,Math.min(100,v*100)):0;
 return <div className={`rb2-doc-metric rb2-doc-metric--${colored(item,mode)}`}>
    <span>{cellValue(item,mode)}</span>
    <div className="rb2-doc-bar" aria-hidden="true"><div style={{width:`${width}%`}}/></div>
 </div>;
}
export default function DocumentComparison({detail,models,onOpenDocument}){
 const [mode,setMode]=useState("recall");
 const [query,setQuery]=useState("");
 const [sort,setSort]=useState("risk");
 const [type,setType]=useState("all");
 const [piiFilter,setPiiFilter]=useState("all");

 const all=useMemo(()=>allDocuments(detail,models),[detail,models]);
 const extensions=useMemo(()=>[...new Set(all.map(x=>x.extension))].sort(),[all]);

 const docPiiMap=useMemo(()=>{
  const map=new Map();
  for(const doc of all){
   map.set(doc.caseId,docPiiSummary(doc,models));
  }
  return map;
 },[all,models]);

 const {piiTypeOptions,missedTypeOptions,statusCounts}=useMemo(()=>{
  const recognizedCounts=new Map();
  const missedCounts=new Map();
  let allRecognized=0;
  let hasRecognized=0;
  let hasMissed=0;
  let zeroGold=0;
  let aBeatsB=0;
  let bBeatsA=0;

  for(const doc of all){
   const info=docPiiMap.get(doc.caseId);
   if(!info)continue;
   if(info.isAllRecognized)allRecognized++;
   if(info.hasRecognized)hasRecognized++;
   if(info.hasMissed)hasMissed++;
   if(info.isZeroGold)zeroGold++;

   if(models.length===2&&doc.metrics.length>=2){
    const rA=doc.metrics[0]?.recall;
    const rB=doc.metrics[1]?.recall;
    if(isNumber(rA)&&isNumber(rB)){
     if(rA>rB)aBeatsB++;
     else if(rB>rA)bBeatsA++;
    }
   }

   for(const t of info.recognizedTypes){
    recognizedCounts.set(t,(recognizedCounts.get(t)||0)+1);
   }
   for(const t of info.missedTypes){
    missedCounts.set(t,(missedCounts.get(t)||0)+1);
   }
  }

  const piiTypeOptions=[...recognizedCounts.entries()]
   .map(([t,count])=>({type:t,label:piiTypeLabel(t),count}))
   .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));

  const missedTypeOptions=[...missedCounts.entries()]
   .map(([t,count])=>({type:t,label:piiTypeLabel(t),count}))
   .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));

  return {
   piiTypeOptions,
   missedTypeOptions,
   statusCounts:{
    allRecognized,
    hasRecognized,
    hasMissed,
    zeroGold,
    aBeatsB,
    bBeatsA,
   },
  };
 },[all,docPiiMap,models]);

 const filtered=useMemo(()=>all.filter(x=>{
  const info=docPiiMap.get(x.caseId);

  if(type!=="all"&&x.extension!==type)return false;

  const q=query.trim().toLowerCase();
  if(q){
   const matchesId=x.caseId.toLowerCase().includes(q);
   const matchesPii=info?.searchString?.includes(q);
   if(!matchesId&&!matchesPii)return false;
  }

  if(piiFilter==="all")return true;
  if(piiFilter==="status:all_recognized")return info?.isAllRecognized;
  if(piiFilter==="status:has_recognized")return info?.hasRecognized;
  if(piiFilter==="status:has_missed")return info?.hasMissed;
  if(piiFilter==="status:zero_gold")return info?.isZeroGold;

  if(piiFilter==="compare:a_beats_b"){
   const rA=x.metrics[0]?.recall;
   const rB=x.metrics[1]?.recall;
   return isNumber(rA)&&isNumber(rB)&&rA>rB;
  }
  if(piiFilter==="compare:b_beats_a"){
   const rA=x.metrics[0]?.recall;
   const rB=x.metrics[1]?.recall;
   return isNumber(rA)&&isNumber(rB)&&rB>rA;
  }

  if(piiFilter.startsWith("type:")){
   const targetType=piiFilter.slice(5);
   return Boolean(info?.recognizedByType?.has(targetType));
  }
  if(piiFilter.startsWith("missed:")){
   const targetType=piiFilter.slice(7);
   return Boolean(info?.missedByType?.has(targetType));
  }

  return true;
 }).sort((a,b)=>{
  if(sort==="name")return a.caseId.localeCompare(b.caseId);
  if(sort==="diff"){
   const difference=x=>x.metrics.length<2?-1:
     (isNumber(x.metrics[0][mode])&&isNumber(x.metrics[1][mode]))?Math.abs(x.metrics[0][mode]-x.metrics[1][mode]):-1;
   return difference(b)-difference(a) || a.caseId.localeCompare(b.caseId);
  }
  const risk=x=>{
   if(x.metrics.some(m=>m.status==="failed"))return 1e7;
   return Math.max(...x.metrics.map(m=>m.fn??0),0) * 10 +
     Math.max(...x.metrics.map(m=>m.leakage??0),0)*100;
  };
  return risk(b)-risk(a)||a.caseId.localeCompare(b.caseId);
 }),[all,docPiiMap,query,sort,type,piiFilter,mode]);

 const hasActiveFilters=query.trim()!==""||type!=="all"||piiFilter!=="all";
 const resetFilters=()=>{
  setQuery("");
  setType("all");
  setPiiFilter("all");
 };

 const maxFn=Math.max(1,...all.flatMap(d=>d.metrics.map(m=>m.fn??0)));
 const delta=d=>d.metrics.length>1&&isNumber(d.metrics[0][mode])&&isNumber(d.metrics[1][mode]) ?
   mode==="fn"?d.metrics[1].fn-d.metrics[0].fn:d.metrics[1][mode]-d.metrics[0][mode]:null;
 const fileType=x=>({xlsx:"XLS",xls:"XLS",csv:"CSV",pdf:"PDF",docx:"DOC",doc:"DOC",txt:"TXT",pptx:"PPT",eml:"EML",jpg:"IMG",png:"IMG"}[x]??x.toUpperCase());

 return <section className="rb2-docs">
  <div className="rb2-page-heading"><div><span className="rb2-kicker">PANORAMICA / DOCUMENTI</span><h1>Document comparison</h1><p>Dove i modelli trovano le PII. E dove le perdono.</p></div>
   <span className="rb2-doc-count">{filtered.length===all.length ? `${all.length} documenti` : `${filtered.length} di ${all.length} documenti`}</span></div>
  <div className="rb2-doc-tools">
    <label className="rb2-doc-search"><span aria-hidden="true">⌕</span><input aria-label="Cerca documento o valore PII" value={query} placeholder="Cerca documento o valore PII…" onChange={e=>setQuery(e.target.value)}/></label>
    <label>Tipo <select value={type} onChange={e=>setType(e.target.value)}><option value="all">Tutti</option>{extensions.map(ext=><option key={ext} value={ext}>{fileType(ext)}</option>)}</select></label>
    <label className="rb2-doc-pii-select-label">PII riconosciuto <select value={piiFilter} onChange={e=>setPiiFilter(e.target.value)}>
      <option value="all">Tutti ({all.length})</option>
      <optgroup label="Stato di riconoscimento">
        <option value="status:all_recognized">100% recall / Tutte riconosciute ({statusCounts.allRecognized})</option>
        <option value="status:has_recognized">Almeno 1 PII riconosciuta ({statusCounts.hasRecognized})</option>
        <option value="status:has_missed">Con PII mancate / leakage ({statusCounts.hasMissed})</option>
        {statusCounts.zeroGold > 0 && <option value="status:zero_gold">Senza PII gold ({statusCounts.zeroGold})</option>}
      </optgroup>
      {models.length===2 && (statusCounts.aBeatsB > 0 || statusCounts.bBeatsA > 0) && (
        <optgroup label="Confronto modelli">
          {statusCounts.aBeatsB > 0 && <option value="compare:a_beats_b">{shortModel(models[0])} supera {shortModel(models[1])} ({statusCounts.aBeatsB})</option>}
          {statusCounts.bBeatsA > 0 && <option value="compare:b_beats_a">{shortModel(models[1])} supera {shortModel(models[0])} ({statusCounts.bBeatsA})</option>}
        </optgroup>
      )}
      {piiTypeOptions.length > 0 && (
        <optgroup label="Tipo di PII riconosciuta">
          {piiTypeOptions.map(opt => (
            <option key={opt.type} value={`type:${opt.type}`}>
              {opt.label} ({opt.count})
            </option>
          ))}
        </optgroup>
      )}
      {missedTypeOptions.length > 0 && (
        <optgroup label="Tipo di PII mancata (leakage)">
          {missedTypeOptions.map(opt => (
            <option key={opt.type} value={`missed:${opt.type}`}>
              {opt.label} ({opt.count})
            </option>
          ))}
        </optgroup>
      )}
    </select></label>
    <label>Metrica <select value={mode} onChange={e=>setMode(e.target.value)}>{Object.entries(modeNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
    <label>Ordina <select value={sort} onChange={e=>setSort(e.target.value)}><option value="risk">Più critici</option><option value="diff">Differenze maggiori</option><option value="name">Nome</option></select></label>
    {hasActiveFilters && <button type="button" className="rb2-doc-filter-clear" onClick={resetFilters} title="Azzera tutti i filtri">Azzera filtri</button>}
  </div>
  <div className="rb2-doc-matrix" role="region" aria-label="Confronto per documento" tabIndex={0}>
    <table><thead><tr><th>Documento</th><th>PII gold</th>{models.map(x=><th key={x}>{shortModel(x)}</th>)}{models.length===2&&<th>Δ {modeNames[mode]} B−A</th>}</tr></thead>
    <tbody>{filtered.map(doc=>{
      const diff=delta(doc);
      const info=docPiiMap.get(doc.caseId);
      const recognized=info?.recognizedTypes ?? [];
      return <tr key={doc.caseId}>
        <td><button className="rb2-doc-open" type="button" onClick={()=>onOpenDocument(doc.caseId,models[0])}>
         <span className={`rb2-file-badge rb2-file-badge--${doc.extension}`}>{fileType(doc.extension)}</span>
         <span className="rb2-doc-meta">
           <strong>{doc.caseId}</strong>
           <small>{doc.humanReviewed?"Gold revisionato":"Gold non revisionato"}</small>
           {recognized.length > 0 && (
             <span className="rb2-doc-pii-chips" aria-label="PII riconosciute">
               {recognized.slice(0, 3).map(t => {
                 const isSelected=piiFilter===`type:${t}`;
                 const recModels=info?.recognizedByType?.get(t);
                 const missModels=info?.missedByType?.get(t);
                 const isPartial=Boolean(missModels && missModels.size > 0);
                 const title=`PII riconosciuta da ${[...(recModels||[])].map(shortModel).join(", ")}${isPartial ? ` (mancata da ${[...missModels].map(shortModel).join(", ")})` : ""}`;
                 return (
                   <span
                     key={t}
                     className={`rb2-pii-chip ${isPartial ? "rb2-pii-chip--partial" : ""} ${isSelected ? "rb2-pii-chip--active" : ""}`}
                     title={`${title} · Clicca per filtrare`}
                     onClick={(e)=>{
                       e.stopPropagation();
                       setPiiFilter(curr=>curr===`type:${t}` ? "all" : `type:${t}`);
                     }}
                   >
                     {piiTypeLabel(t)}
                   </span>
                 );
               })}
               {recognized.length > 3 && (
                 <span
                   className="rb2-pii-chip rb2-pii-chip--more"
                   title={recognized.slice(3).map(piiTypeLabel).join(", ")}
                 >
                   +{recognized.length - 3}
                 </span>
               )}
             </span>
           )}
         </span></button></td>
        <td className="rb2-doc-num">{doc.goldCount.toLocaleString("it-IT")}</td>
        {doc.metrics.map(m=><td key={m.model}><DocMetric item={m} mode={mode} maxFn={maxFn}/></td>)}
        {models.length===2&&<td className="rb2-doc-delta">{isNumber(diff)?`${diff>0?"+":""}${mode==="fn"?diff:(diff*100).toFixed(1)+" pp"}`:"—"}</td>}
      </tr>
    })}</tbody></table>
  </div>
  {!filtered.length&&<div className="rb2-empty"><p>Nessun documento trovato con i filtri attuali.</p>{hasActiveFilters && <button type="button" className="rb2-doc-filter-clear" onClick={resetFilters}>Azzera filtri</button>}</div>}
  <div className="rb2-doc-footer"><div><span className="rb2-dot rb2-dot--good"/> Buona copertura</div><div><span className="rb2-dot rb2-dot--caution"/> Da verificare</div><div><span className="rb2-dot rb2-dot--risk"/> PII esposte / critiche</div><p>Le percentuali usano sempre una scala comune. “Run fallito” non equivale a recall 0%. Gli errori sono riferiti al gold del benchmark.</p></div>
 </section>;
}
