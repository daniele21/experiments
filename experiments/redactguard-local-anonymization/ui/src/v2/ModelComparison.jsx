import { useMemo, useState } from "react";
import { compareInsight, isNumber, modelEvidence, ratioText, shortModel, timeText, isSameSuite } from "./evidence";
import "./model.css";

const MODES = [
  {key:"protection", icon:"◈", label:"Protezione", caption:"Quante PII restano esposte?"},
  {key:"speed", icon:"⚡", label:"Velocità", caption:"Quanto dura un'inferenza?"},
  {key:"tradeoff", icon:"◎", label:"Trade-off", caption:"Quale compromesso conviene?"},
];
const pct = x => isNumber(x) ? `${Math.max(0,Math.min(100,x*100))}%` : "0%";
function MetricGauge({value,label,kind="protection"}) {
  const safe = kind==="speed" ? null : value;
  return <div className="rb2-gauge">
    <span className="rb2-gauge__track"><span className="rb2-gauge__fill" style={{width:pct(safe)}} /></span>
    <span className="rb2-gauge__label">{label}</span>
  </div>;
}
function ComparisonCard({model,focus,best}) {
  const main = focus==="speed" ? timeText(model.p50) :
    focus==="tradeoff" ? ratioText(model.recall) :
    model.zeroCount===null ? "—" : `${model.zeroCount} / ${model.total}`;
  const mainLabel = focus==="speed"?"Latenza p50 · 3 documenti campione":
    focus==="tradeoff" ? `Recall bilanciato per ${model.qualityBase==="family"?"famiglia":"documento"}`:
    "Documenti senza leakage";
  return <article className={`rb2-model-card ${best?"rb2-model-card--leader":""}`}>
    <div className="rb2-model-card__head">
      <div className="rb2-model-card__icon" aria-hidden="true">⬡</div>
      <div><span className="rb2-model-card__eyebrow">MODELLO</span><h3 title={model.model}>{shortModel(model.model)}</h3></div>
      {best && <span className="rb2-leader">Migliore in questo criterio</span>}
    </div>
    <div className="rb2-model-card__hero">
      <span className="rb2-model-card__number">{main}</span>
      <span className="rb2-model-card__label">{mainLabel}</span>
    </div>
    {focus==="protection" ? <>
      <MetricGauge value={model.zeroRate} label={ratioText(model.zeroRate)+" dei documenti"} />
      <div className="rb2-model-card__foot">
        <div><span>Recall per famiglia</span><strong>{ratioText(model.recall)}</strong></div>
        <div><span>PII mancate</span><strong>{model.falseNegatives??"—"}</strong></div>
      </div>
    </> : focus==="speed" ? <>
      <div className="rb2-model-card__foot rb2-model-card__foot--spaced">
        <div><span>p95 esplorativo</span><strong>{timeText(model.p95)}</strong></div>
        <div><span>Campioni</span><strong>{model.sampleCount ?? "—"}</strong></div>
      </div>
      <p className="rb2-model-note">{model.cacheVerified ? "Risposte non servite dalla cache Korgis." : "Latenza non verificata: nessun confronto di velocità."}</p>
    </> : <>
      <MetricGauge value={model.recall} label={ratioText(model.recall)+" recall bilanciato"} />
      <div className="rb2-model-card__foot">
        <div><span>Velocità p50</span><strong>{timeText(model.p50)}</strong></div>
        <div><span>Precisione micro</span><strong>{ratioText(model.precision)}</strong></div>
      </div>
    </>}
  </article>;
}
export default function ModelComparison({detail,models,onOpenDocuments}) {
 const [focus,setFocus]=useState("protection");
 const evidence=useMemo(()=>models.map(m=>modelEvidence(detail,m)),[detail,models]);
 const [a,b]=evidence;
 const validCompare=isSameSuite(detail);
 const best = !validCompare || !a || !b ? null :
    focus==="speed" ? (isNumber(a.p50)&&isNumber(b.p50)&&a.p50!==b.p50 ? a.p50<b.p50?a.model:b.model:null):
    focus==="tradeoff" ? null :
    isNumber(a.zeroRate)&&isNumber(b.zeroRate)&&a.zeroRate!==b.zeroRate ? a.zeroRate>b.zeroRate?a.model:b.model:null;
 const summary=validCompare?compareInsight(a,b,focus):
   "Prove provenienti da run diversi o incompleti: non è possibile indicare un vincitore.";
 const subcopy=focus==="speed"?
   "La velocità è misurata su inferenze reali; il p95 resta esplorativo con pochi campioni.":
   focus==="tradeoff"?"Non esiste un modello migliore per qualsiasi esigenza: confronta protezione e tempo di risposta.":
   "Il criterio principale è quanti documenti risultano senza PII annotate esposte.";
 const stats=focus==="speed" ? [
    {label:"Protocollo",value:a?.latencyCases&&b?.latencyCases?`${a.latencyCases} documenti`:"Non verificato"},
    {label:"Campioni per modello",value:a?.sampleCount??"—"},
    {label:"Base",value:"p50 latenza senza cache"},
  ] : [
    {label:"Protezione bilanciata",value:"Recall macro per famiglia"},
    {label:"Qualità globale (micro)",value:a&&b?`${ratioText(a.microRecall)} / ${ratioText(b.microRecall)}`:"—"},
    {label:"Precisione micro",value:a&&b?`${ratioText(a.precision)} / ${ratioText(b.precision)}`:"—"},
 ];
 return <section className="rb2-model">
  <div className="rb2-page-heading"><div>
    <span className="rb2-kicker">PANORAMICA / MODELLI</span>
    <h1>Model comparison</h1>
    <p>Due modelli. Una domanda alla volta.</p>
  </div><span className={`rb2-status ${validCompare?"rb2-status--ok":"rb2-status--warn"}`}>{validCompare?"Run completato":"Dati misti o incompleti"}</span></div>
  <div className="rb2-mode-tabs" role="tablist" aria-label="Criterio di confronto">
   {MODES.map(x=><button key={x.key} type="button" className={focus===x.key?"active":""} role="tab" aria-selected={focus===x.key} onClick={()=>setFocus(x.key)}>
    <span className="rb2-mode-tabs__icon" aria-hidden="true">{x.icon}</span><span><strong>{x.label}</strong><small>{x.caption}</small></span></button>)}
  </div>
  <div className="rb2-model-takeaway"><span className="rb2-kicker">IL RISULTATO IN BREVE</span><h2>{summary}</h2><p>{subcopy}</p></div>
  <div className="rb2-model-cards">{evidence.map(x=><ComparisonCard key={x.model} model={x} focus={focus} best={x.model===best}/>)}</div>
  <div className="rb2-model-footer">
   <div className="rb2-model-footer__summary">
    <span className="rb2-kicker">COSA CAMBIA DAVVERO</span>
    <div className="rb2-fact-grid">{stats.map(x=><div key={x.label}><span>{x.label}</span><strong>{x.value}</strong></div>)}</div>
    <p className="rb2-fineprint">{evidence.some(e=>!e.humanReviewed)?"Gold non revisionato manualmente · risultati sperimentali. ":""}{focus==="speed" && a?.sampleCount ? `p95 basato su ${a.sampleCount} campioni: considerarlo esplorativo.`:""} {detail?.summary?.source==="overview"?"Cross-run non omogeneo: non interpretare come test controllato.":""}</p>
   </div>
   <button type="button" className="rb2-primary-action" onClick={onOpenDocuments}>Scopri dove differiscono <span aria-hidden="true">→</span></button>
  </div>
 </section>;
}
