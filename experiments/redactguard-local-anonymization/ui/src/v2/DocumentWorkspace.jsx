import { useEffect, useMemo, useRef, useState } from "react";
import { documentEvidence, modelsIn, shortModel, spansForModel, spanKey, ratioText } from "./evidence";
import "./workspace.css";

const WINDOW = 4800;
const TYPE_NAMES = {private_person:"Nome",private_email:"Email",private_phone:"Telefono",private_address:"Indirizzo",private_date:"Data",account_number:"Identificativo"};
const TYPE_LABEL = x => TYPE_NAMES[x] ?? String(x??"PII").replaceAll("_"," ");
function clipped(v){return Math.max(0,v);}
function Canvas({doc,model,selected,onSelect,showDifferences,revealed,onReveal,windowStart,scrollRef,onScroll}){
 const result=useMemo(()=>spansForModel(doc,model),[doc,model]);
 const text=doc.text ?? "";
 const until=Math.min(text.length,windowStart+WINDOW);
 const visible=useMemo(()=>{
   const kept=result.items.filter(s=>s.end>windowStart && s.start<until && (!showDifferences||s.status!=="detected"))
     .sort((a,b)=>a.start-b.start || (a.status==="missed"?-1:1));
   const parts=[];let pos=windowStart;
   for (const span of kept) {
     if(span.start<pos)continue; // overlaps: one label per visible position
     if(span.start>pos)parts.push({text:text.slice(pos,span.start),kind:"plain",id:`text-${pos}`});
     parts.push({span,kind:"pii",id:spanKey(span)});
     pos=span.end;
   }
   if(pos<until)parts.push({text:text.slice(pos,until),kind:"plain",id:`text-${pos}`});
   return parts;
 },[result,text,windowStart,until,showDifferences]);
 const current = doc.metrics.find(m=>m.model===model);
 return <div className="rb2-pane">
  <header className="rb2-pane-head">
   <div className="rb2-pane-title"><span className="rb2-pane-model-dot"/><strong title={model}>{shortModel(model)}</strong></div>
   <span className={current?.status==="ok"?"rb2-pane-good":"rb2-pane-fail"}>{current?.status==="ok" ? `${ratioText(current.recall)} recall` : "Inferenza non valida"}</span>
  </header>
  {current?.status!=="ok" && <div role="status" className="rb2-canvas-warning">Output non valido o non disponibile: il testo è mostrato come riferimento, non come protezione riuscita.</div>}
  {result.invalidOffsets>0 && <div className="rb2-canvas-warning" role="status">{result.invalidOffsets} annotazioni escluse per offset non coerente con il testo canonico.</div>}
  <div className="rb2-pane-scroll" ref={scrollRef} onScroll={onScroll}>
   {!text ? <div className="rb2-workspace-empty">Testo canonico non disponibile in questa suite.</div> :
    <div className="rb2-paper" aria-label={`Testo canonico di ${doc.caseId}, modello ${model}`}>
     {windowStart>0 && <p className="rb2-paper-info">… estratto dal carattere {windowStart.toLocaleString("it-IT")}</p>}
     <div className="rb2-paper-content">
      {visible.map(part=>{
       if(part.kind==="plain")return <span key={part.id}>{part.text}</span>;
       const s=part.span,id=part.id;
       const selectedHere=selected?.start===s.start && selected?.end===s.end && selected?.pii_type===s.pii_type;
       const open=revealed.has(`${model}|${id}`);
       return <button key={id} type="button" data-rb2-focus={selectedHere ? "true":undefined}
        className={`rb2-inline-pii rb2-inline-pii--${s.status} ${selectedHere?"rb2-inline-pii--selected":""}`}
        aria-label={`${TYPE_LABEL(s.pii_type)} ${s.status==="missed"?"mancata":s.status==="extra"?"extra":"rilevata"}; ${open?"nascondi":"esamina"} valore`}
        onClick={()=>{onSelect(s);}} title={`${TYPE_LABEL(s.pii_type)} · ${s.status}`}>
        {open?s.value:`[ ${TYPE_LABEL(s.pii_type).toUpperCase()} ]`}
       </button>;
      })}
     </div>
     {until<text.length && <p className="rb2-paper-info">… visualizzati {(until-windowStart).toLocaleString("it-IT")} di {text.length.toLocaleString("it-IT")} caratteri. Naviga al segmento successivo.</p>}
    </div>}
  </div>
  {text.length>WINDOW && <footer className="rb2-pane-pagination">
   <span>{(windowStart+1).toLocaleString("it-IT")}–{until.toLocaleString("it-IT")} / {text.length.toLocaleString("it-IT")} caratteri</span>
   <div><button type="button" disabled={windowStart===0} onClick={()=>onSelect({navigateTo:clipped(windowStart-WINDOW)})}>← Precedente</button>
    <button type="button" disabled={until>=text.length} onClick={()=>onSelect({navigateTo:until})}>Successivo →</button></div>
  </footer>}
 </div>;
}
function EvidenceList({doc,model,tab,selected,onSelect}){
 const raw=doc.metrics.find(x=>x.model===model)?.raw;
 const from=tab==="missed" ? raw?.missed??[] : tab==="extra" ? raw?.overRedacted??[] : raw?.identified??[];
 if(!from.length) return <div className="rb2-inspector-empty">Nessuna annotazione in questa categoria.</div>;
 return <div className="rb2-issue-list">{from.slice(0,500).map((span,i)=>{
 const id=spanKey(span);
 const active=selected?.start===span.start && selected?.end===span.end && selected?.pii_type===span.pii_type;
 return <button key={`${id}-${i}`} type="button" className={active?"active":""} onClick={()=>onSelect(span)}><span className={`rb2-issue-indicator rb2-issue-indicator--${tab}`}/><span><strong>{TYPE_LABEL(span.pii_type)}</strong><small>Caratteri {span.start}–{span.end}</small></span><span aria-hidden="true">›</span></button>;
 })}{from.length>500&&<p className="rb2-paper-info">Visualizzate le prime 500 annotazioni. Filtra per tipo o naviga al documento.</p>}</div>;
}
export default function DocumentWorkspace({detail,documentName,models,initialModel,onBack,onSelectModel}){
 const doc=useMemo(()=>documentEvidence(detail,documentName,models),[detail,documentName,models]);
 const [current,setCurrent]=useState(initialModel??models[0]);
 const [sideBySide,setSideBySide]=useState(true);
 const [showDifferences,setShowDifferences]=useState(false);
 const [inspectorOpen,setInspectorOpen]=useState(true);
 const [tab,setTab]=useState("overview");
 const [selected,setSelected]=useState(null);
 const [revealed,setRevealed]=useState(new Set());
 const [windowStart,setWindowStart]=useState(0);
 const leftRef=useRef(null),rightRef=useRef(null),scrollingRef=useRef(false);
 const active=models.includes(current)?current:models[0];
 const other=models.find(m=>m!==active);
 useEffect(()=>{setCurrent(initialModel??models[0]);setSelected(null);setRevealed(new Set());setWindowStart(0);setTab("overview");},[documentName,initialModel,detail?.summary?.key]);
 useEffect(()=>{setRevealed(new Set());},[active,other]);
 useEffect(()=>{
   if(!selected||!Number.isInteger(selected.start))return;
   const scrollTarget=Math.max(0,Math.floor(Math.max(0,selected.start-400)/WINDOW)*WINDOW);
   setWindowStart(scrollTarget);
 },[selected]);
 useEffect(()=>{
   if(!selected)return;
   const target=leftRef.current?.querySelector('[data-rb2-focus="true"]')||rightRef.current?.querySelector('[data-rb2-focus="true"]');
   target?.scrollIntoView?.({block:"center",behavior:"auto"});
 },[windowStart,selected,showDifferences]);
 const chooseSpan=(x)=>{
   if(Number.isInteger(x?.navigateTo)){setWindowStart(x.navigateTo);setSelected(null);}
   else{setSelected(x);setInspectorOpen(true);}
 };
 const syncScroll=(from)=>{
   if(scrollingRef.current)return;
   const otherRef=from==="left"?rightRef.current:leftRef.current;
   const source=from==="left"?leftRef.current:rightRef.current;
   if(!source||!otherRef)return;
   scrollingRef.current=true;
   otherRef.scrollTop=source.scrollTop;
   requestAnimationFrame(()=>{scrollingRef.current=false;});
 };
 const raw=doc.metrics.find(m=>m.model===active)?.raw;
 const missed=raw?.missed?.length??0, extra=raw?.overRedacted?.length??0, detected=raw?.identified?.length??0;
 const rawStatus=doc.metrics.find(m=>m.model===active);
 const selectedKey=selected?spanKey(selected):null;
 const revealedKey=`${active}|${selectedKey}`;
 const selectedShown=selectedKey && revealed.has(revealedKey);
 const toggleReveal=()=>{
   if(!selectedKey)return;
   setRevealed(old=>{const next=new Set(old);if(next.has(revealedKey))next.delete(revealedKey);else next.add(revealedKey);return next;});
 };
 return <section className="rb2-workspace">
  <div className="rb2-workspace-top"><button className="rb2-back" type="button" onClick={onBack}>← Documenti</button><span className="rb2-workspace-breadcrumb">/ <strong>{documentName}</strong></span><span className="rb2-workspace-meta">{doc.goldCount.toLocaleString("it-IT")} PII gold · {doc.extension.toUpperCase()}</span></div>
  <div className="rb2-workspace-controls">
   <div className="rb2-workspace-title"><span className="rb2-file-icon">▤</span><div><h1>{documentName}</h1><p>Testo canonico valutato nel benchmark · {doc.humanReviewed?"Gold revisionato":"Gold non revisionato"}</p></div></div>
   <div className="rb2-workspace-buttons"><label className="rb2-workspace-select">Modello <select aria-label="Modello principale" value={active} onChange={e=>{setCurrent(e.target.value);onSelectModel?.(e.target.value);}}>{models.map(m=><option value={m} key={m}>{shortModel(m)}</option>)}</select></label>
   {models.length>1&&<button type="button" className={sideBySide?"active":""} aria-pressed={sideBySide} onClick={()=>setSideBySide(x=>!x)}>Affiancato</button>}
   <button type="button" aria-pressed={showDifferences} className={showDifferences?"active":""} onClick={()=>setShowDifferences(x=>!x)}>Solo differenze</button>
   <button type="button" aria-expanded={inspectorOpen} onClick={()=>setInspectorOpen(x=>!x)}>Inspector {inspectorOpen?"◀":"▶"}</button></div>
  </div>
  <div className={`rb2-workspace-layout ${inspectorOpen?"":"rb2-workspace-layout--full"}`}>
    <div className="rb2-workspace-canvas">
     <div className="rb2-canvas-legend"><span><i className="rb2-key--detected"/> Rilevata</span><span><i className="rb2-key--missed"/> Mancata</span><span><i className="rb2-key--extra"/> Extra rispetto al gold</span><span className="rb2-legend-note">I valori annotati sono mascherati</span></div>
     <div className={`rb2-canvas-grid ${sideBySide&&other?"rb2-canvas-grid--split":""}`}>
      <Canvas doc={doc} model={active} selected={selected} onSelect={chooseSpan} showDifferences={showDifferences} revealed={revealed} onReveal={toggleReveal} windowStart={windowStart} scrollRef={leftRef} onScroll={()=>syncScroll("left")}/>
      {sideBySide&&other&&<Canvas doc={doc} model={other} selected={selected} onSelect={chooseSpan} showDifferences={showDifferences} revealed={revealed} onReveal={toggleReveal} windowStart={windowStart} scrollRef={rightRef} onScroll={()=>syncScroll("right")}/>}
     </div>
    </div>
    {inspectorOpen&&<aside className="rb2-inspector" aria-label="Analisi PII del documento">
     <div className="rb2-inspector-heading"><div><span className="rb2-kicker">PII INSPECTOR</span><h2>Analisi delle annotazioni</h2></div><button type="button" aria-label="Chiudi inspector" onClick={()=>setInspectorOpen(false)}>×</button></div>
     <div className="rb2-inspector-tabs" role="tablist" aria-label="Categoria PII">{[["overview","Riepilogo"],["missed",`Mancate ${missed}`],["extra",`Extra ${extra}`],["detected","Rilevate"],["raw","Raw"]].map(([value,label])=><button key={value} type="button" role="tab" aria-selected={tab===value} className={tab===value?"active":""} onClick={()=>setTab(value)}>{label}</button>)}</div>
     {tab==="overview"?<div className="rb2-inspector-body">
      <div className="rb2-inspector-stats"><div><strong>{ratioText(rawStatus?.recall)}</strong><span>Recall sul documento</span></div><div><strong>{detected}</strong><span>PII individuate</span></div><div className={missed?"rb2-risk":""}><strong>{missed}</strong><span>PII mancate</span></div><div><strong>{extra}</strong><span>Extra vs gold</span></div></div>
      <h3>Problemi da verificare</h3>
      {missed+extra>0?<div className="rb2-inspector-actions">{missed>0&&<button type="button" onClick={()=>setTab("missed")}>Esamina {missed} PII mancate →</button>}{extra>0&&<button type="button" onClick={()=>setTab("extra")}>Esamina {extra} extra →</button>}</div>:<p className="rb2-inspector-muted">Nessuna anomalia annotata per questo modello.</p>}
      {rawStatus?.status!=="ok"&&<p className="rb2-canvas-warning">Risposta non valida: risultati di qualità non disponibili.</p>}
     </div>:tab==="raw"?<div className="rb2-inspector-body"><h3>Evidenza tecnica</h3><p>Stato: <strong>{rawStatus?.status??"n/d"}</strong></p><p>Output strutturato completo conservato nei file JSONL del run locale. Nessun dato raw non mascherato viene esposto qui automaticamente.</p>{rawStatus?.error&&<p className="rb2-canvas-warning">Errore inferenza. Consulta il JSONL locale per dettagli non filtrati.</p>}</div>:
      <EvidenceList doc={doc} model={active} tab={tab} selected={selected} onSelect={chooseSpan}/>}
     {selected&&<div className="rb2-selection"><span className="rb2-kicker">ANNOTAZIONE SELEZIONATA</span><strong>{TYPE_LABEL(selected.pii_type)}</strong><small>Offset {selected.start}–{selected.end}</small><div className="rb2-selection-status">{selected.status==="missed"?"Non rilevata dal modello":selected.status==="extra"?"Extra rispetto al gold":"Rilevata"}</div><button type="button" onClick={toggleReveal}>{selectedShown?"Nascondi valore":"Rivela valore annotato"}</button></div>}
    </aside>}
  </div>
 </section>;
}
