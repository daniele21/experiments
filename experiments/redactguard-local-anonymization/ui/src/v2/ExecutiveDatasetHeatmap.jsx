import { useMemo, useState } from "react";
import { buildModelDatasetMatrix, MATRIX_METRICS, matrixMetric, matrixTone } from "./capabilityMatrix";
import { shortModel } from "./evidence";
import { nextHeatmapSort, sortExecutiveRows } from "./heatmapSort";

const fmt=x=>x===null?"—":`${(x*100).toFixed(1)}%`;
const toneText=t=>({good:"favorevole",medium:"intermedio",low:"critico",unavailable:"non disponibile"})[t];
export default function ExecutiveDatasetHeatmap({latest,modelFilter,onOpenRun}) {
 const [metric,setMetric]=useState("recall");
 const [sort,setSort]=useState({column:"model",direction:"asc"});
 const {datasets,rows}=useMemo(()=>buildModelDatasetMatrix(latest),[latest]);
 const selected=useMemo(()=>sortExecutiveRows(
   rows.filter(r=>modelFilter.has(r.modelId)),sort,metric,
 ),[rows,modelFilter,sort,metric]);
 const order=(column)=>setSort(current=>nextHeatmapSort(current,column,metric));
 const ariaSort=column=>sort.column===column
   ? (sort.direction==="asc"?"ascending":"descending") : "none";
 const arrow=column=>sort.column!==column?"↕":sort.direction==="asc"?"↑":"↓";
 return <section className="rb3-panel rb3-heatmap">
 <div className="rb3-section-head">
  <div><span className="rb2-kicker">QUATTRO CAPACITÀ, UN CONFRONTO</span><h2>Performance per dataset</h2>
    <p>La stessa metrica per tutti i modelli, senza medie tra dataset diversi.</p></div>
  <label>Metrica
   <select aria-label="Metrica della heatmap" value={metric} onChange={e=>{setMetric(e.target.value);setSort({column:"model",direction:"asc"});}}>
     {MATRIX_METRICS.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}
   </select></label>
 </div>
 <div className="rb3-heatmap-scroll" role="region" tabIndex={0} aria-label="Performance dei modelli per dataset">
 <table>
  <thead><tr><th scope="col" aria-sort={ariaSort("model")}>
    <button type="button" className="rb3-th-sort" onClick={()=>order("model")}
       aria-label="Ordina per nome modello">Modello <span aria-hidden="true">{arrow("model")}</span></button></th>
    {datasets.map(d=><th key={d.id} scope="col" aria-sort={ariaSort(d.id)}>
      <button type="button" className="rb3-th-sort" onClick={()=>order(d.id)}
         aria-label={`Ordina per ${d.title}, ${MATRIX_METRICS.find(m=>m.id===metric)?.label}`}>
         {d.title}<span aria-hidden="true">{arrow(d.id)}</span></button></th>)}</tr></thead>
  <tbody>{selected.map(row=><tr key={row.modelId}>
    <th scope="row">{shortModel(row.modelId)}</th>
    {datasets.map(d=>{
      const m=row.cells[d.id];
      const value=matrixMetric(m,metric), tone=matrixTone(value,metric);
      return <td key={d.id}>
        {m && value!==null ? <button type="button" className={`rb3-heatmap-value rb3-heatmap-value--${tone}`}
          aria-label={`${row.modelId}, ${d.title}, ${MATRIX_METRICS.find(x=>x.id===metric)?.label}: ${fmt(value)}; ${toneText(tone)}. Apri il run.`}
          title={`Apri ${m.suiteId??m.runKey} · ${m.comparability??"nessuna verifica"}`}
          onClick={()=>onOpenRun(m.runKey,row.modelId)}>
          <strong>{fmt(value)}</strong><small>{m.comparability==="different_protocol"?"⚠ Protocollo diverso":"↗ Dettaglio"}</small>
        </button> : <div className="rb3-heatmap-na" title={m?"Metrica non misurata":"Modello non testato su questo dataset"}>—</div>}
      </td>;
    })}
   </tr>)}</tbody>
 </table>
 </div>
 {selected.length===0&&<p className="rb3-empty-inline">Seleziona un modello per visualizzare la matrice.</p>}
 <div className="rb3-scale"><span><i className="rb3-key-good"/> {metric==="fp"?"Pochi FP":"Alto"}</span>
   <span><i className="rb3-key-mid"/> Intermedio</span><span><i className="rb3-key-low"/> {metric==="fp"?"Molti FP":"Basso"}</span>
   <span>— Non misurato</span></div>
 <p className="rb3-micro">Clicca l’intestazione di una colonna per ordinare i modelli; un secondo clic inverte l’ordine. Clicca una cella per analizzare il run originale. Le colorazioni utilizzano soglie assolute uguali per tutti i dataset.</p>
 </section>;
}
