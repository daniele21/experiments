import { useMemo } from "react";
import { percentage, valid } from "./executiveAnalytics";

const COLORS=["#62adff","#40d8ba","#eeb06b","#b29cff","#fa8f9c","#85c966","#d18bf7","#f0cd5f"];
export function modelColor(modelId, allModelIds=[]) {
 const sorted=[...new Set(allModelIds)].sort((a,b)=>a.localeCompare(b,"en",{numeric:true}));
 const n=sorted.indexOf(modelId);
 return COLORS[(n<0?0:n)%COLORS.length];
}
const pct=x=>`${Math.round(x*100)}%`;
function ticks(low,high,steps=5){
 return Array.from({length:steps+1},(_,i)=>low+(high-low)*i/steps);
}
const asCoord=(v,min,max,low,range)=>{
 if(!valid(v)||!Number.isFinite(max)||max===min)return null;
 return low+(v-min)/(max-min)*range;
};

export default function ExecutiveParetoChart({frontier,mode,modelIds,onOpenModel}) {
 const privacy=mode==="privacy";
 const layout=useMemo(()=>{
   const W=920,H=430,L=75,R=35,T=29,B=64,w=W-L-R,h=H-T-B;
   const points=frontier.points.filter(p=>p.eligible && valid(p.x)&&valid(p.y));
   const maxX=privacy ? 1 : Math.max(...points.map(x=>x.x),1)*1.12;
   const minX=privacy ? 0 : Math.min(...points.map(x=>x.x),maxX/2)*.82;
   const lowX=minX<maxX?minX:0;
   const X=v=>asCoord(v,lowX,maxX,L,w);
   const Y=v=>asCoord(v,0,1,T+h,-h);
   const coords=points.map(p=>({...p,cx:X(p.x),cy:Y(p.y)}));
   const curve=frontier.frontier
    .filter(p=>valid(p.x)&&valid(p.y))
    .sort((a,b)=>a.x-b.x)
    .map(p=>[X(p.x),Y(p.y)]);
   return {W,H,L,R,T,B,w,h,coords,curve,minX:lowX,maxX,X,Y};
 },[frontier,privacy]);
 const {W,H,L,T,h,w,coords,curve,minX,maxX,X,Y}=layout;
 const label=privacy?"Falsi positivi nei casi negativi · meno è meglio":"Latenza p50 senza cache (ms) · meno è meglio";
 const title=privacy?"Protezione vs over-redaction":"Protezione vs latenza reale";
 const colors=Object.fromEntries(modelIds.map(id=>[id,modelColor(id,modelIds)]));
 if(coords.length===0)return <div className="rb3-chart-empty" role="status">
   <strong>Nessun confronto valido disponibile</strong>
   <p>{privacy?"Servono almeno recall sui positivi e casi negativi validi per i modelli selezionati.":"Questa vista richiede almeno due modelli misurati senza cache nella stessa suite, con qualità e latenza disponibili."}</p>
 </div>;
 const formatX=x=>privacy?pct(x):`${Math.round(x).toLocaleString("it-IT")}`;
 const frontierLine=curve.map((p,i)=>`${i===0?"M":"L"} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
 return <div className="rb3-chart-wrap">
 <div className="rb3-chart-title">
  <div><strong>{title}</strong><span>{privacy?"Dataset selezionato: qualità più alta, falsi positivi più bassi":"Solo misure dello stesso workload; p50 osservata"}</span></div>
  <span className="rb3-frontier-label">◈ {frontier.frontier.length} in frontiera</span>
 </div>
 <svg className="rb3-scatter" viewBox={`0 0 ${W} ${H}`} role="img"
 aria-label={`Pareto frontier: ${coords.length} modelli. ${label}. Asse verticale recall PII`}>
  {ticks(0,1,5).map((v,i)=><g key={`y${i}`}>
    <line x1={L} y1={Y(v)} x2={L+w} y2={Y(v)} stroke="#42546a" strokeDasharray="4 7" opacity={.65}/>
    <text x={L-12} y={Y(v)+4} textAnchor="end" fill="#98abc3" fontSize="12">{pct(v)}</text>
  </g>)}
  {ticks(minX,maxX,5).map((v,i)=><g key={`x${i}`}>
    <line x1={X(v)} y1={T} x2={X(v)} y2={T+h} stroke="#344961" strokeDasharray="4 8" opacity={.65}/>
    <text x={X(v)} y={T+h+22} textAnchor="middle" fill="#98abc3" fontSize="12">{formatX(v)}</text>
  </g>)}
  <line x1={L} y1={T+h} x2={L+w} y2={T+h} stroke="#7790ad"/>
  <line x1={L} y1={T} x2={L} y2={T+h} stroke="#7790ad"/>
  <text x={L+w/2} y={H-9} textAnchor="middle" fill="#a9bdd5" fontSize="13">{label}</text>
  <text transform={`translate(18,${T+h/2}) rotate(-90)`} textAnchor="middle" fill="#a9bdd5" fontSize="13">Recall PII · più è meglio</text>
  {curve.length>1&&<path d={frontierLine} fill="none" stroke="#44dbbd" strokeWidth="2.5" strokeDasharray="5 4" opacity=".9"/>}
  {coords.map(p=><g key={p.modelId}
    role="button" tabIndex={0} aria-label={`Apri ${p.modelId}; recall ${percentage(p.y)}, ${privacy?"falsi positivi "+percentage(p.x):"latenza "+Math.round(p.x)+" millisecondi"}; ${p.frontier?"non dominato":"dominato"}`}
    onClick={()=>onOpenModel(p.modelId,p.runKey)}
    onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onOpenModel(p.modelId,p.runKey);}}}
    style={{cursor:"pointer"}}>
    <title>{p.modelId} · Recall {percentage(p.y)} · {privacy?"FP "+percentage(p.x):"p50 "+Math.round(p.x)+" ms"} · {p.frontier?"Pareto":"Dominato"}</title>
    <circle cx={p.cx} cy={p.cy} r={p.frontier?15:11} stroke={colors[p.modelId]} strokeWidth={p.frontier?3:2} fill="#112237" opacity={p.dominated?.73:1}/>
    <circle cx={p.cx} cy={p.cy} r={p.frontier?9:6} fill={colors[p.modelId]} opacity={p.dominated?.65:1}/>
    <text x={p.cx} y={p.cy-21} textAnchor="middle" fill="#dbeaf8" fontSize="12" fontWeight="600">{p.modelId.replace("qwen3.5-","Qwen ").replace("nemotron-nano-","Nemotron ")}</text>
   </g>)}
  </svg>
 <div className="rb3-chart-legend">
  {coords.map(p=><button type="button" key={p.modelId} onClick={()=>onOpenModel(p.modelId,p.runKey)}>
    <i style={{backgroundColor:colors[p.modelId]}}/><strong>{p.modelId}</strong>
    <span>{p.frontier?"Frontiera":"Dominato"}</span>
  </button>)}
 </div>
 </div>;
}
