import { useMemo, useState } from "react";
import { shortModel } from "./evidence";
import { buildModelDatasetMatrix, MATRIX_METRICS, matrixMetric, matrixTone } from "./capabilityMatrix";
import "./capability-matrix.css";

const pct = value => value === null ? "—" : `${(value * 100).toFixed(1)}%`;
const safePct = value => value === null ? "0%" : `${Math.round(value * 100)}%`;
const info = (m, metric) => {
  if (!m) return "Non testato";
  if (metric === "fp") return m.negativeCases > 0
    ? `${m.negativeValidated} / ${m.negativeCases} negativi validi` : "Nessun caso negativo";
  if (metric === "recall") return m.totalGold > 0
    ? `${m.totalGold} PII gold · ${m.validDocuments ?? "?"}/${m.documents ?? "?"} casi validi`
    : "Nessuna PII gold";
  return `${m.validDocuments} / ${m.documents} documenti`;
};
const title = (m,dataset,metric) => {
 const value=matrixMetric(m,metric);
 const rows=[
 `${m.modelId} · ${dataset.title}`,
 `${MATRIX_METRICS.find(x=>x.id===metric)?.label}: ${pct(value)}`,
 info(m,metric),
 `Run: ${m.suiteId ?? m.runKey ?? "non identificato"}`,
 `Comparabilità: ${m.comparability==="different_protocol"?"protocollo diverso":m.comparability==="unverified"?"non verificata":m.comparability==="reference"?"riferimento":"verificata"}`,
 ];
 return rows.join("\n");
};
const toneName = (tone,metric) => ({
  good:metric==="fp"?"Pochi falsi positivi":"Buona copertura",
  medium:"Intermedio",
  low:metric==="fp"?"Molti falsi positivi":"Bassa copertura",
  unavailable:"Dato non disponibile",
})[tone];

function MatrixCell({model,dataset,metric,onSelect,compact=false}) {
 if (!model) {
   return <div className="rb2-matrix-empty"><span>—</span><small>Non testato</small></div>;
 }
 const value=matrixMetric(model,metric);
 const tone=matrixTone(value,metric);
 return <button
   type="button"
   className={`rb2-matrix-cell rb2-matrix-cell--${tone} ${compact?"rb2-matrix-cell--compact":""}`}
   title={title(model,dataset,metric)}
   aria-label={`${model.modelId}, ${dataset.title}, ${MATRIX_METRICS.find(x=>x.id===metric)?.label}: ${pct(value)}. Apri dettaglio.`}
   onClick={()=>onSelect(dataset.id,model.modelId)}>
   <span className="rb2-matrix-cell__head">
      <strong>{pct(value)}</strong>
      <span className="rb2-matrix-cell__chevron" aria-hidden="true">↗</span>
   </span>
   <span className="rb2-matrix-cell__track" aria-hidden="true"><span style={{width:safePct(value)}}/></span>
   <small>{info(model,metric)}</small>
   {model.comparability==="different_protocol"&&<span className="rb2-matrix-cell__warning">! Configurazione diversa</span>}
   {model.comparability==="unverified"&&<span className="rb2-matrix-cell__caution">? Confronto non verificato</span>}
 </button>;
}

export default function CapabilityMatrix({latest,onSelectCell}) {
 const [metric,setMetric]=useState("recall");
 const {datasets,rows,measured}=useMemo(()=>buildModelDatasetMatrix(latest),[latest]);
 const current=MATRIX_METRICS.find(x=>x.id===metric);
 return <div className="rb2-matrix">
   <div className="rb2-matrix-head">
     <div>
       <span className="rb2-kicker">CONFRONTO TRASVERSALE</span>
       <h2>Modelli × dataset</h2>
       <p>Ogni riga è un modello; ogni colonna è una capacità. I valori provengono dall'ultimo run disponibile del modello su quel dataset.</p>
     </div>
     <div className="rb2-matrix-stats" aria-label="Copertura benchmark">
       <div><strong>{rows.length}</strong><small>modelli</small></div>
       <div><strong>{datasets.length}</strong><small>dataset</small></div>
       <div><strong>{measured}</strong><small>risultati</small></div>
     </div>
   </div>
   <div className="rb2-matrix-toolbar">
     <div className="rb2-matrix-metrics" role="group" aria-label="Seleziona metrica della matrice">
       {MATRIX_METRICS.map(x=><button type="button" key={x.id} className={metric===x.id?"active":""}
          aria-pressed={metric===x.id} onClick={()=>setMetric(x.id)}>
          {x.label}
       </button>)}
     </div>
     <div className="rb2-matrix-scale" aria-label="Legenda semantica">
       <span><i className="rb2-matrix-dot rb2-matrix-dot--good"/> {metric==="fp"?"Basso":"Alto"}</span>
       <span><i className="rb2-matrix-dot rb2-matrix-dot--medium"/> Intermedio</span>
       <span><i className="rb2-matrix-dot rb2-matrix-dot--low"/> {metric==="fp"?"Alto":"Basso"}</span>
     </div>
   </div>
   <p className="rb2-matrix-help">{current?.description} Scala assoluta 0–100% per ogni cella; un valore identico ha sempre lo stesso colore.</p>
   {rows.length === 0 ? <div className="rb2-cap-empty">
       <h3>Nessun modello testato</h3><p>Esegui una suite per popolare il confronto.</p>
     </div> : <>
     <div className="rb2-matrix-table-wrap" role="region" aria-label="Matrice prestazioni modelli per dataset" tabIndex={0}>
       <table className="rb2-matrix-table">
         <thead><tr>
           <th scope="col"><span>Modello</span><small>Ultimo risultato per dataset</small></th>
           {datasets.map(d=><th key={d.id} scope="col"><strong>{d.title}</strong>
             <small>{d.report?.datasetId??"Non testato"}</small></th>)}
         </tr></thead>
         <tbody>{rows.map(row=><tr key={row.modelId}>
           <th scope="row"><strong>{shortModel(row.modelId)}</strong><small>{datasets.filter(d=>Boolean(row.cells[d.id])).length} / {datasets.length} dataset</small></th>
           {datasets.map(d=><td key={d.id}><MatrixCell model={row.cells[d.id]} dataset={d} metric={metric} onSelect={onSelectCell}/></td>)}
         </tr>)}</tbody>
       </table>
     </div>
     <div className="rb2-matrix-mobile">
       {rows.map(row=><article key={row.modelId} className="rb2-matrix-mobile-model">
         <h3>{shortModel(row.modelId)}</h3>
         {datasets.map(d=><div key={d.id} className="rb2-matrix-mobile-row">
           <div className="rb2-matrix-mobile-row__label"><strong>{d.title}</strong></div>
           <MatrixCell model={row.cells[d.id]} dataset={d} metric={metric} onSelect={onSelectCell} compact/>
         </div>)}
       </article>)}
     </div>
   </>}
   <p className="rb2-cap-note">Clicca una cella per esplorare gli errori del modello in quel dataset. Le difficoltà dei dataset non sono equivalenti: non calcolare una media dei punteggi tra colonne. Un run con configurazione diversa è contrassegnato, non trattato come pienamente confrontabile.</p>
 </div>;
}
