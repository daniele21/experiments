import { ArrowUpRight, Check, ChevronRight, Copy, Info, Layers3, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { bytes, capabilityLabel, milliseconds, percent, score } from '../utils';
import { getHardwareComparability, peakAttribution, peakRss } from './hardwareEvidence';
import {
  cockpitDatasets, cockpitDecision, cockpitMetricLeader, cockpitMetricValue,
  type CockpitMetric, type CockpitModels,
} from './compareCockpitLogic';
import './compareCockpit.css';

const LETTERS = ['A', 'B', 'C'] as const;
const COLORS = ['var(--dc-a)', 'var(--dc-b)', 'var(--dc-c)'];
type Detail = 'quality' | 'speed' | 'reliability' | 'datasets' | 'latency-plot' | 'memory-plot' | 'hardware' | 'evidence' | 'share';
const DETAILS: Record<Detail, string> = {
  quality: 'Aggregate quality', speed: 'Observed P50 latency', reliability: 'Benchmark failure rate',
  datasets: 'Exact dataset evidence', 'latency-plot': 'Quality × Latency',
  'memory-plot': 'Quality × Peak RAM', hardware: 'Hardware and resource telemetry',
  evidence: 'Evidence & comparability', share: 'Share comparison',
};

function displayMetric(metric: CockpitMetric, value: number | null) {
  if (value == null) return '—';
  if (metric === 'quality') return score(value);
  if (metric === 'speed') return milliseconds(value);
  if (metric === 'reliability') return percent(value);
  return bytes(value);
}

function MiniPlot({ selected, field, metric, expanded = false }: {
  selected: CockpitModels; field: DecisionModelSummary[]; metric: 'speed' | 'memory'; expanded?: boolean;
}) {
  const valid = field.filter(m => {
    const x = cockpitMetricValue(m, metric);
    return x != null && x > 0 && cockpitMetricValue(m, 'quality') != null;
  });
  if (valid.length < 2) return <div className="dc-chart-empty">Not enough measured points</div>;
  const w = expanded ? 660 : 260, h = expanded ? 320 : 124;
  const left = expanded ? 54 : 20, right = expanded ? 630 : 246;
  const top = expanded ? 26 : 15, bottom = expanded ? 272 : 99;
  const values = valid.map(m => cockpitMetricValue(m, metric)!);
  const xTransform = (value: number) => metric === 'speed' ? Math.log10(value) : value / (1024 ** 3);
  const transformed = values.map(xTransform);
  const lo = Math.min(...transformed), hi = Math.max(...transformed);
  const span = Math.max(0.15, hi - lo);
  const xmin = metric === 'speed' ? lo - span * 0.1 : 0;
  const xmax = hi + span * 0.13 + (metric === 'speed' ? 0 : Math.max(.1, hi*.02));
  const x = (m: DecisionModelSummary) => left + ((xTransform(cockpitMetricValue(m, metric)!) - xmin) / Math.max(.01, xmax-xmin)) * (right-left);
  const y = (m: DecisionModelSummary) => bottom - (Math.max(0,Math.min(100,cockpitMetricValue(m,'quality')!))/100) * (bottom-top);
  const selectedIds = new Set(selected.map(m=>m.model_key));
  const dot = expanded ? 15 : 10;
  return <svg viewBox={'0 0 '+w+' '+h} className="dc-plot" role="img"
    aria-label={'Quality versus ' + (metric === 'speed' ? 'observed P50 latency' : 'sampled peak process RSS') + ', selected models highlighted'}>
    {[.25,.5,.75].map(t=><g key={t}>
      <line x1={left} y1={bottom-(bottom-top)*t} x2={right} y2={bottom-(bottom-top)*t} className="dc-plot-grid"/>
      {expanded && <text x={left-9} y={bottom-(bottom-top)*t+4} textAnchor="end" className="dc-plot-tick">{Math.round(t*100)}</text>}
    </g>)}
    <path d={'M'+left+' '+top+'V'+bottom+'H'+right} className="dc-plot-axis"/>
    {valid.filter(m=>!selectedIds.has(m.model_key)).map(m=><circle key={m.model_signature} cx={x(m)} cy={y(m)} r={expanded?5:3} className="dc-other-point">
      <title>{m.model_key}: quality {displayMetric('quality',cockpitMetricValue(m,'quality'))}, {displayMetric(metric,cockpitMetricValue(m,metric))}</title>
    </circle>)}
    {selected.map((m,i)=>cockpitMetricValue(m,metric)!=null && cockpitMetricValue(m,'quality')!=null ?
      <g key={m.model_key}>
        <circle cx={x(m)} cy={y(m)} r={dot} fill={COLORS[i]} stroke="#fff" strokeWidth={expanded?3:2}/>
        <text x={x(m)} y={y(m)+(expanded?5:3.5)} textAnchor="middle" className={'dc-plot-letter'+(expanded?' big':'')}>{LETTERS[i]}</text>
        <title>{m.model_key}: quality {displayMetric('quality',cockpitMetricValue(m,'quality'))}; {displayMetric(metric,cockpitMetricValue(m,metric))}</title>
      </g> : null)}
    {expanded ? <>
      <text x={w/2} y={h-12} textAnchor="middle" className="dc-plot-axis-title">{metric==='speed'?'Observed P50 latency (log scale) →':'Observed peak process RSS (GiB) →'}</text>
      <text transform={'translate(16 '+h/2+') rotate(-90)'} textAnchor="middle" className="dc-plot-axis-title">Quality ↑</text>
    </> : <>
      <text x={left} y={h-3} className="dc-plot-axis-caption">↑ Quality</text>
      <text x={right} y={h-3} textAnchor="end" className="dc-plot-axis-caption">{metric==='speed'?'P50 (log) →':'RSS (GiB) →'}</text>
    </>}
  </svg>;
}

function StatTile({ metric, models, onClick }: {
  metric: 'quality' | 'speed' | 'reliability'; models: CockpitModels; onClick: () => void;
}) {
  const winner = cockpitMetricLeader(models, metric);
  const value = winner == null ? null : cockpitMetricValue(models[winner],metric);
  const meta = {
    quality: { title:'Quality ↑', foot:'Aggregate score' },
    speed: { title:'P50 Latency ↓', foot:'Observed median' },
    reliability: { title:'Failures ↓', foot:'Benchmark failures' },
  }[metric];
  return <button className="dc-stat dc-clickable" type="button" onClick={onClick} aria-label={'View ' + meta.title + ' breakdown'}>
    <span className="dc-stat-name">{meta.title}</span>
    <strong className="dc-stat-number">{value == null ? '—' : displayMetric(metric,value)}</strong>
    <span className="dc-stat-footer">{winner == null ? 'Incomplete or tied' :
      <>Leader <b style={{color:COLORS[winner]}}>{LETTERS[winner]}</b></>}</span>
  </button>;
}

function MetricsTable({ selected, metric }: { selected: CockpitModels; metric: CockpitMetric }) {
  const leader = cockpitMetricLeader(selected, metric);
  return <div className="dc-modal-table-wrap"><table className="dc-modal-table">
    <thead><tr><th>Model</th><th>Value</th><th>Evidence</th></tr></thead>
    <tbody>{selected.map((m,i)=><tr key={m.model_key}>
      <td><span className={'dc-letter dc-letter-'+LETTERS[i].toLowerCase()}>{LETTERS[i]}</span> {m.model_key}</td>
      <td className={leader===i?'dc-winning':''}>{displayMetric(metric,cockpitMetricValue(m,metric))}</td>
      <td>{metric === 'memory' ? (m.resource_summary?.sample_count == null?'Not sampled':m.resource_summary.sample_count+' samples') : m.observed_case_count+' cases'}</td>
    </tr>)}</tbody>
  </table></div>;
}

function DetailedRows({ selected, datasets }: {
  selected: CockpitModels; datasets: ReturnType<typeof cockpitDatasets>['datasets'];
}) {
  return <div className="dc-modal-table-wrap"><table className="dc-modal-table">
    <thead><tr><th>Task</th>{selected.map((m,i)=><th key={m.model_key}>{LETTERS[i]}</th>)}<th>Winner</th></tr></thead>
    <tbody>{datasets.map(row=><tr key={row.key}>
      <td><strong>{row.dataset}</strong><small>{capabilityLabel(row.capability)}</small></td>
      {row.values.map((value,i)=><td key={i} className={row.winner===i?'dc-winning':''}>
        {value==null?'—':score(value)}<small>{row.samples[i]} cases</small>
      </td>)}
      <td>{row.winner!=null?LETTERS[row.winner]:row.tied?'Tie':'Not comparable'}</td>
    </tr>)}</tbody>
  </table></div>;
}

export function CompareCockpit({ selected, field, datasetRows, onModeChange, onModelChange, onDeepDive }: {
  selected: CockpitModels;
  field: DecisionModelSummary[];
  datasetRows: DecisionDatasetSummary[];
  onModeChange: (three: boolean) => void;
  onModelChange: (position: number, key: string) => void;
  onDeepDive: () => void;
}) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [copied, setCopied] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const report = cockpitDatasets(selected,datasetRows);
  const insight = cockpitDecision(selected,report.shared,report.union);
  const hardware = getHardwareComparability(selected);
  const samePolicy = selected.every(m=>m.quality_policy_id===selected[0].quality_policy_id);
  const qualityAligned = report.shared>0 && report.shared===report.union && samePolicy && selected.every(m=>m.quality_coverage_complete);
  const maxRSS = Math.max(1,...selected.map(m=>peakRss(m)??0));
  useEffect(()=>{
    if (!detail) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const keydown = (event:KeyboardEvent) => {
      if(event.key==='Escape') setDetail(null);
      if(event.key==='Tab') {
        const dialog = closeButtonRef.current?.closest('[role="dialog"]');
        const focusable = [...(dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), a[href]') ?? [])];
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (!first || !last) return;
        if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
      }
    };
    window.addEventListener('keydown',keydown);
    return ()=>{window.removeEventListener('keydown',keydown); previousFocus?.focus();};
  },[detail]);

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
    } catch {
      setCopied(false);
      setDetail('share');
    }
  };
  return <div className="dc-cockpit">
    <header className="dc-topbar">
      <div className="dc-heading"><span className="dc-logo">M</span><h1>Compare <span>/ Decision Cockpit</span></h1></div>
      <div className="dc-header-actions">
        <button className="dc-text-action" type="button" onClick={onDeepDive}>Full analysis <ArrowUpRight size={14}/></button>
        <button className="dc-share" type="button" onClick={share} aria-label="Copy comparison link">
          {copied?<Check size={14}/>:<Copy size={14}/>} <span>{copied?'Copied':'Share'}</span>
        </button>
      </div>
    </header>
    <div className="dc-selectors" aria-label="Models in the comparison">
      <div className="dc-count" role="group" aria-label="Number of models">
        <button type="button" aria-pressed={selected.length===2} className={selected.length===2?'active':''} onClick={()=>onModeChange(false)}>2</button>
        <button type="button" aria-pressed={selected.length===3} className={selected.length===3?'active':''} disabled={field.length<3} onClick={()=>onModeChange(true)}>3</button>
      </div>
      {selected.map((m,i)=><label className="dc-model-picker" key={LETTERS[i]}>
        <span className="dc-model-caption"><i className={'dc-swatch dc-swatch-'+LETTERS[i].toLowerCase()}/>{LETTERS[i]} · Model</span>
        <select value={m.model_key} aria-label={'Model '+LETTERS[i]} onChange={event=>onModelChange(i,event.target.value)}>
          {field.filter(item=>item.model_key===m.model_key || !selected.some(other=>other.model_key===item.model_key))
            .map(item=><option value={item.model_key} key={item.model_key}>{item.model_key}</option>)}
        </select>
      </label>)}
    </div>
    <section className="dc-hero" aria-labelledby="dc-insight-title">
      <div className="dc-hero-content"><span className="dc-kicker">✦ Executive insight</span>
        <h2 id="dc-insight-title">{insight.title}</h2><p>{insight.description}</p></div>
      <div className="dc-leader-chips">
        {(['quality','speed','memory'] as const).map(metric=>{
          const leader=cockpitMetricLeader(selected,metric);
          return <span key={metric}>{metric==='quality'?'Quality':metric==='speed'?'Speed':'RAM'}
            <b style={{color:leader==null?'#8290a5':COLORS[leader]}}>{leader==null?'—':LETTERS[leader]}</b></span>;
        })}
      </div>
    </section>
    <div className="dc-kpi-grid">
      <StatTile metric="quality" models={selected} onClick={()=>setDetail('quality')}/>
      <StatTile metric="speed" models={selected} onClick={()=>setDetail('speed')}/>
      <StatTile metric="reliability" models={selected} onClick={()=>setDetail('reliability')}/>
    </div>
    <div className="dc-workbench">
      <section className="dc-panel dc-task-panel" aria-label="Dataset performance">
        <button className="dc-panel-heading" type="button" onClick={()=>setDetail('datasets')}>
          <strong><Layers3 size={14}/> Dataset performance</strong>
          <small>{report.shared}/{report.union} shared <ChevronRight size={13}/></small>
        </button>
        <div className={'dc-heatmap dc-heatmap-'+selected.length} role="table" aria-label="Normalized quality scores by dataset and model">
          <div className="dc-heatmap-header" role="row"><span role="columnheader">Task</span>{selected.map((m,i)=><span key={m.model_key} role="columnheader">{LETTERS[i]}</span>)}</div>
          <div className="dc-dataset-rows">
            {report.datasets.map(row=><div key={row.key} className="dc-heatmap-row" role="row">
              <span role="rowheader" title={row.dataset}>{row.dataset}</span>
              {row.values.map((value,i)=><span role="cell" key={i}
                className={'dc-heat-cell dc-heat-'+LETTERS[i].toLowerCase()+(row.winner===i?' dc-heat-winner':'')}
                title={LETTERS[i]+' · '+row.dataset+': '+(value==null?'No comparable score':score(value))}
                style={{'--dc-score': value==null?'0%':Math.round(Math.min(100,Math.max(0,value))*.21)+'%'} as CSSProperties}>
                {value==null?'—':score(value)}
              </span>)}
            </div>)}
          </div>
        </div>
        <div className="dc-task-footer">
          <div className="dc-wins">{report.wins.map((n,i)=><span key={i} className={'dc-win-'+LETTERS[i].toLowerCase()}>{LETTERS[i]} · {n}</span>)} <span>{report.ties} ties</span></div>
          <button type="button" onClick={()=>setDetail('datasets')}>All scores <ArrowUpRight size={12}/></button>
        </div>
      </section>
      <div className="dc-plots">
        {([['speed','latency-plot','Quality × Latency','P50 · observed'],['memory','memory-plot','Quality × Peak RAM','Peak process RSS']] as const).map(([metric,key,label,sub])=>
          <button className="dc-panel dc-chart-card" type="button" key={key} onClick={()=>setDetail(key)}
            aria-label={'Expand '+label}>
            <span className="dc-chart-title"><strong>{label}</strong><small>{sub} <ArrowUpRight size={12}/></small></span>
            <MiniPlot selected={selected} field={field} metric={metric}/>
          </button>)}
      </div>
    </div>
    <section className="dc-panel dc-hardware">
      <button className="dc-panel-heading" type="button" onClick={()=>setDetail('hardware')}>
        <strong>Peak RAM & Hardware</strong><small>{hardware.status==='matched'?'Reported hosts match':hardware.status==='mismatch'?'Different hosts':'Host comparison limited'} <ChevronRight size={13}/></small>
      </button>
      <div className="dc-hardware-content">
        <div className="dc-ram-rows">{selected.map((m,i)=>{
          const rss=peakRss(m);
          return <div className="dc-ram-row" key={m.model_key}>
            <b className={'dc-color-'+LETTERS[i].toLowerCase()}>{LETTERS[i]}</b>
            <div className="dc-ram-track"><i style={{width:rss==null?'0%':Math.max(2,rss/maxRSS*100)+'%',background:COLORS[i]}}/></div>
            <strong>{rss==null?'—':bytes(rss)}</strong>
          </div>;
        })}</div>
        <div className="dc-host-list">{selected.map((m,i)=>{
          const host=peakAttribution(m);return <div key={m.model_key} title={host.provenance}>
            <span className={'dc-color-'+LETTERS[i].toLowerCase()}>{LETTERS[i]}</span>
            <span>{host.environment?.cpu_model||'Device not recorded'}</span>
          </div>;
        })}</div>
      </div>
    </section>
    <button className={'dc-evidence '+(qualityAligned&&hardware.status==='matched'?'positive':'caution')} type="button"
      onClick={()=>setDetail('evidence')}>
      <span className="dc-evidence-icon">{qualityAligned?'✓':'!'}</span>
      <span className="dc-evidence-text"><strong>{report.shared}/{report.union} shared scored datasets</strong>
        <small>{!qualityAligned?'Coverage / policy needs review':hardware.status==='matched'?'Reported host specs match · latency is observed':'Hardware context differs or is incomplete'}</small></span>
      <ChevronRight size={15}/>
    </button>

    {detail && <div className="dc-detail-layer" role="presentation">
      <button className="dc-detail-backdrop" aria-label="Close detail" type="button" onClick={()=>setDetail(null)}/>
      <section className="dc-detail" role="dialog" aria-modal="true" aria-label={DETAILS[detail]}>
        <div className="dc-detail-header"><div><span className="dc-kicker">MCB · measurement detail</span><h2>{DETAILS[detail]}</h2></div>
          <button type="button" ref={closeButtonRef} className="dc-close" aria-label="Close detail" onClick={()=>setDetail(null)}><X size={19}/></button></div>
        {(['quality','speed','reliability'] as const).includes(detail as 'quality'|'speed'|'reliability') ?
          <><MetricsTable selected={selected} metric={detail as 'quality'|'speed'|'reliability'}/>
            <p className="dc-detail-note">All values are observed benchmark aggregates. A leader is shown only when every selected model has a valid measurement and the result is not tied.</p></> : null}
        {detail==='datasets' && <><DetailedRows selected={selected} datasets={report.datasets}/>
          <p className="dc-detail-note">A winner is assigned only on datasets with valid scores for every selected model. Near-equal scores (±0.05 points) count as ties.</p></>}
        {(detail==='latency-plot'||detail==='memory-plot')&&<><div className="dc-expanded-chart"><MiniPlot selected={selected} field={field} metric={detail==='latency-plot'?'speed':'memory'} expanded/></div>
          <p className="dc-detail-note">{detail==='latency-plot'?'Observed P50 latency depends on the execution environment.':'RSS is sampled resident memory of the measured process, not total unified/Metal memory.'} Missing measurements are not plotted.</p></>}
        {detail==='hardware'&&<><MetricsTable selected={selected} metric="memory"/><div className="dc-host-detail">
          {selected.map((m,i)=>{const item=peakAttribution(m);return <div key={m.model_key}><strong>{LETTERS[i]} · {m.model_key}</strong>
            <p>Host: {item.environment?.cpu_model||'Not recorded'} · {item.environment?.machine||'—'} · {item.environment?.total_memory_bytes?bytes(item.environment.total_memory_bytes):'RAM unknown'}</p>
            <p>Peak run: {item.peakRunId||'Unverified'} · {item.provenance} · scope: {m.resource_summary?.scope||'unavailable'}</p>
            <p>Mean RSS: {bytes(m.resource_summary?.process_rss_bytes_avg)} · accelerator peak: {bytes(m.resource_summary?.accelerator_memory_bytes_peak)}</p>
          </div>})}</div><p className="dc-detail-note">{hardware.detail} RSS may not include total system/Metal allocations, and the maximum can be from a different run than aggregate quality.</p></>}
        {detail==='share' && <div className="dc-share-fallback">
          <p>Copy this link to share the same selected models and comparison mode.</p>
          <input aria-label="Comparison URL" readOnly value={window.location.href}
            onFocus={event=>event.target.select()} onClick={event=>event.currentTarget.select()}/>
        </div>}
        {detail==='evidence'&&<div className="dc-evidence-explain">
          <p><Info size={15}/> <strong>Scored datasets:</strong> {report.shared} shared of {report.union} across selected models.</p>
          <p><Info size={15}/> <strong>Quality policy:</strong> {samePolicy?'Same policy reported':'Different quality policies'}; {qualityAligned?'coverage complete':'some coverage incomplete or unmatched'}.</p>
          <p><Info size={15}/> <strong>Hardware:</strong> {hardware.detail}</p>
          <p><Info size={15}/> <strong>Interpretation:</strong> latency and RSS are observed, not hardware-normalized. Inspect the run-level evidence before deployment decisions.</p>
        </div>}
        <div className="dc-detail-actions"><button type="button" className="dc-deep-link" onClick={()=>{setDetail(null);onDeepDive();}}>Open full analysis <ArrowUpRight size={14}/></button>
          <button type="button" onClick={()=>setDetail(null)}>Close</button></div>
      </section>
    </div>}
  </div>;
}
