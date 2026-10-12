import { useMemo, useState } from "react";
import { allDocuments, isNumber, modelsIn, ratioText, shortModel } from "./evidence";
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
 const all=useMemo(()=>allDocuments(detail,models),[detail,models]);
 const extensions=useMemo(()=>[...new Set(all.map(x=>x.extension))].sort(),[all]);
 const filtered=useMemo(()=>all.filter(x=>{
  return (type==="all"||x.extension===type) && x.caseId.toLowerCase().includes(query.trim().toLowerCase());
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
 }),[all,query,sort,type,mode]);
 const maxFn=Math.max(1,...all.flatMap(d=>d.metrics.map(m=>m.fn??0)));
 const delta=d=>d.metrics.length>1&&isNumber(d.metrics[0][mode])&&isNumber(d.metrics[1][mode]) ?
   mode==="fn"?d.metrics[1].fn-d.metrics[0].fn:d.metrics[1][mode]-d.metrics[0][mode]:null;
 const fileType=x=>({xlsx:"XLS",xls:"XLS",csv:"CSV",pdf:"PDF",docx:"DOC",doc:"DOC",txt:"TXT",pptx:"PPT",eml:"EML",jpg:"IMG",png:"IMG"}[x]??x.toUpperCase());
 return <section className="rb2-docs">
  <div className="rb2-page-heading"><div><span className="rb2-kicker">PANORAMICA / DOCUMENTI</span><h1>Document comparison</h1><p>Dove i modelli trovano le PII. E dove le perdono.</p></div>
   <span className="rb2-doc-count">{all.length} documenti</span></div>
  <div className="rb2-doc-tools">
    <label className="rb2-doc-search"><span aria-hidden="true">⌕</span><input aria-label="Cerca documento" value={query} placeholder="Cerca documento…" onChange={e=>setQuery(e.target.value)}/></label>
    <label>Tipo <select value={type} onChange={e=>setType(e.target.value)}><option value="all">Tutti</option>{extensions.map(ext=><option key={ext} value={ext}>{fileType(ext)}</option>)}</select></label>
    <label>Metrica <select value={mode} onChange={e=>setMode(e.target.value)}>{Object.entries(modeNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
    <label>Ordina <select value={sort} onChange={e=>setSort(e.target.value)}><option value="risk">Più critici</option><option value="diff">Differenze maggiori</option><option value="name">Nome</option></select></label>
  </div>
  <div className="rb2-doc-matrix" role="region" aria-label="Confronto per documento" tabIndex={0}>
    <table><thead><tr><th>Documento</th><th>PII gold</th>{models.map(x=><th key={x}>{shortModel(x)}</th>)}{models.length===2&&<th>Δ {modeNames[mode]} B−A</th>}</tr></thead>
    <tbody>{filtered.map(doc=>{
      const diff=delta(doc);
      return <tr key={doc.caseId}>
        <td><button className="rb2-doc-open" type="button" onClick={()=>onOpenDocument(doc.caseId,models[0])}>
         <span className={`rb2-file-badge rb2-file-badge--${doc.extension}`}>{fileType(doc.extension)}</span><span><strong>{doc.caseId}</strong><small>{doc.humanReviewed?"Gold revisionato":"Gold non revisionato"}</small></span></button></td>
        <td className="rb2-doc-num">{doc.goldCount.toLocaleString("it-IT")}</td>
        {doc.metrics.map(m=><td key={m.model}><DocMetric item={m} mode={mode} maxFn={maxFn}/></td>)}
        {models.length===2&&<td className="rb2-doc-delta">{isNumber(diff)?`${diff>0?"+":""}${mode==="fn"?diff:(diff*100).toFixed(1)+" pp"}`:"—"}</td>}
      </tr>
    })}</tbody></table>
  </div>
  {!filtered.length&&<div className="rb2-empty">Nessun documento trovato. Modifica i filtri.</div>}
  <div className="rb2-doc-footer"><div><span className="rb2-dot rb2-dot--good"/> Buona copertura</div><div><span className="rb2-dot rb2-dot--caution"/> Da verificare</div><div><span className="rb2-dot rb2-dot--risk"/> PII esposte / critiche</div><p>Le percentuali usano sempre una scala comune. “Run fallito” non equivale a recall 0%. Gli errori sono riferiti al gold del benchmark.</p></div>
 </section>;
}
