import { AlertTriangle, CheckCircle2, ChevronDown, Clock3, Gauge, Info, Layers3, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { bytes, capabilityLabel, milliseconds, percent, providerCostValue, score } from '../utils';
import {
  leaderIndices, sharedThreeDatasets, threeDecisionInsight,
  type ComparePreference, type ThreeDatasetRow, type ThreeModels,
} from './compareThreeLogic';
import './compareThree.css';

const LABELS = ['A', 'B', 'C'] as const;
const PREFERENCES: Array<[ComparePreference, string]> = [
  ['balanced', 'Balanced'], ['quality', 'Quality'], ['speed', 'Speed'], ['reliability', 'Reliability'],
];

function ThreeHeading({ step, title, description, aside }: {
  step: string; title: string; description: string; aside?: ReactNode;
}) {
  return <div className="cmp-section-heading">
    <div><span className="cmp-eyebrow">{step}</span><h2>{title}</h2><p>{description}</p></div>
    {aside}
  </div>;
}

function ThreeMetric({ title, icon, values, format, lowerBetter, footnote }: {
  title: string; icon: ReactNode;
  values: Array<number | null | undefined>;
  format: (n: number | null | undefined) => string;
  lowerBetter: boolean; footnote: string;
}) {
  const leaders = leaderIndices(values, lowerBetter);
  const maximum = Math.max(1e-9, ...values.filter((value): value is number => value != null && Number.isFinite(value)));
  const titleLabel = leaders.length === 1 ? 'Model ' + LABELS[leaders[0]] + ' leads' : leaders.length > 1 ? 'Shared lead' : 'Insufficient evidence';
  return <article className="cmp-metric-card cmp3-metric">
    <div className="cmp-metric-title">{icon}<span>{title}</span></div>
    <div className={'cmp3-winner-label ' + (leaders.length === 1 ? 'cmp3-tone-' + LABELS[leaders[0]].toLowerCase() : '')}>{titleLabel}</div>
    <div className="cmp3-three-bars">
      {values.map((value, index) => <div key={LABELS[index]} className={'cmp3-three-bar' + (leaders.includes(index) ? ' leader' : '')}>
        <strong className={'cmp3-tone-' + LABELS[index].toLowerCase()}>{LABELS[index]}</strong>
        <div className="cmp-bar-track"><i className={'cmp3-bar-' + LABELS[index].toLowerCase()} style={{ width: value == null ? '0%' : Math.max(0, value) / maximum * 100 + '%' }}/></div>
        <b>{format(value)}</b>
      </div>)}
    </div>
    <div className="cmp-metric-footnote">{footnote}</div>
  </article>;
}

function ThreeScoreRows({ rows, unionCount, wins, ties }: {
  rows: ThreeDatasetRow[]; unionCount: number; wins: [number, number, number]; ties: number;
}) {
  const maxSpread = rows[0]?.spread ?? 0;
  const outlier = rows.length > 2 && maxSpread >= 15 && maxSpread >= 3 * Math.max(rows[1].spread, 0.01) ? rows[0] : null;
  const plotted = outlier ? rows.slice(1) : rows;
  return <section className="cmp-section">
    <ThreeHeading step="02 / Dataset intelligence" title="Which model wins each task?"
      description="Scores are plotted on the same 0–100 scale across datasets. The leading model is marked for each task."
      aside={<div className="cmp-win-summary">
        {wins.map((n, i) => <span key={LABELS[i]} className={'cmp3-tone-' + LABELS[i].toLowerCase()}>{n} {LABELS[i]} wins</span>)}
        <span>{ties} ties</span>
      </div>}/>
    {outlier && <div className="cmp3-outlier">
      <div><span className="cmp-eyebrow">Largest gap · inspect cases</span><strong>{outlier.dataset}</strong><small>{capabilityLabel(outlier.capability)}</small></div>
      <div><b>{maxSpread.toFixed(1)} pts</b><small>max–min gap</small></div>
      <div className="cmp3-outlier-scores">
        {outlier.scores.map((value, i) => <span key={LABELS[i]} className={'cmp3-tone-' + LABELS[i].toLowerCase()}>{LABELS[i]} {score(value)}</span>)}
      </div>
    </div>}
    {plotted.length ? <div className="cmp3-datasets">
      <div className="cmp3-dataset-head"><span>Capability / dataset</span><span>Shared quality scale · higher is better →</span><span>Leader</span></div>
      {plotted.map(row => <div className="cmp3-dataset-row" key={row.key}>
        <div className="cmp3-dataset-title"><strong>{row.dataset}</strong><small>{capabilityLabel(row.capability)}</small></div>
        <div className="cmp3-dataset-bars" aria-label={LABELS.map((label,i)=> label + ' ' + score(row.scores[i])).join(', ')}>
          {row.scores.map((value, i) => <div className="cmp3-dataset-bar" key={LABELS[i]}>
            <span className={'cmp3-tone-' + LABELS[i].toLowerCase()}>{LABELS[i]}</span>
            <div className="cmp3-dataset-track"><i className={'cmp3-bar-' + LABELS[i].toLowerCase()} style={{ width: Math.min(100,Math.max(0,value)) + '%' }}/></div>
            <b className={row.winners.includes(i) ? 'cmp3-leading-score' : ''}>{score(value)}</b>
          </div>)}
        </div>
        <div className="cmp3-task-leader">{row.winners.length === 1
          ? <strong className={'cmp3-tone-' + LABELS[row.winners[0]].toLowerCase()}>{LABELS[row.winners[0]]}<small>+{row.spread.toFixed(1)} spread</small></strong>
          : <span>Tie</span>}</div>
      </div>)}
    </div> : <p className="cmp-note">No shared datasets with valid scores for all three models.</p>}
    <p className="cmp-note">Shared scored datasets: {rows.length} / {unionCount}. {outlier ? 'The largest outlier is displayed separately, using exact scores.' : ''} A tie means the leaders differ by at most 0.05 quality points. All three scores must be present for a dataset to count.</p>
  </section>;
}

function ThreeScatter({ field, selected }: { field: DecisionModelSummary[]; selected: ThreeModels }) {
  const plotted = field.filter(m => m.overall_quality_score != null && Number.isFinite(m.overall_quality_score) &&
    m.latency_p50_ms != null && Number.isFinite(m.latency_p50_ms) && m.latency_p50_ms > 0);
  if (plotted.length < 2) return <div className="cmp-note">Not enough model results with quality and observed latency.</div>;
  const lxs = plotted.map(m => Math.log10(m.latency_p50_ms!));
  const xMin = Math.min(...lxs), xMax = Math.max(...lxs);
  const padding = Math.max(0.2, (xMax - xMin) * .16);
  const left = xMin - padding, right = xMax + padding;
  const quality = plotted.map(m=>m.overall_quality_score!);
  const bottom = Math.max(0, Math.min(...quality) - 12), top = Math.min(100,Math.max(...quality) + 12);
  const x = (value:number) => 83 + 747 * (Math.log10(value) - left) / (right - left);
  const y = (value:number) => 255 - 212 * (value - bottom) / Math.max(1,top-bottom);
  const selectedKeys = new Set(selected.map(m => m.model_key));
  return <>
    <div className="cmp-scatter-frame cmp3-scatter-frame">
      <svg className="cmp-scatter" viewBox="0 0 900 320" role="img" aria-label="Quality versus observed P50 latency, highlighting models A B and C">
        {Array.from({length:5},(_,i)=>i).map(i => <g key={i}>
          <line className="cmp-grid-line" x1={83 + 747*i/4} x2={83 + 747*i/4} y1="38" y2="255"/>
          <line className="cmp-grid-line" x1="83" x2="830" y1={255 - 212*i/4} y2={255 - 212*i/4}/>
          <text className="cmp-axis-label" x={83 + 747*i/4} y="277" textAnchor="middle">{milliseconds(10 ** (left + (right-left)*i/4))}</text>
          <text className="cmp-axis-label" x="70" y={259 - 212*i/4} textAnchor="end">{(bottom+(top-bottom)*i/4).toFixed(0)}</text>
        </g>)}
        <text className="cmp-axis-title" x="459" y="309" textAnchor="middle">Observed P50 latency · log scale · lower is better ←</text>
        <text className="cmp-axis-title" transform="translate(20,148) rotate(-90)" textAnchor="middle">Quality score ↑</text>
        {plotted.filter(m => !selectedKeys.has(m.model_key)).map(m => <circle key={m.model_signature} className="cmp-other-point" r="5" cx={x(m.latency_p50_ms!)} cy={y(m.overall_quality_score!)}>
          <title>{m.model_key}: {score(m.overall_quality_score)} quality · {milliseconds(m.latency_p50_ms)}</title>
        </circle>)}
        {selected.map((m,i) => m.latency_p50_ms != null && m.latency_p50_ms > 0 && m.overall_quality_score != null ?
          <g key={m.model_key}>
            <circle r="12" cx={x(m.latency_p50_ms)} cy={y(m.overall_quality_score)} className={'cmp3-scatter-point-' + LABELS[i].toLowerCase()}/>
            <text x={x(m.latency_p50_ms)} y={y(m.overall_quality_score) + 4} textAnchor="middle" className="cmp3-scatter-letter">{LABELS[i]}</text>
            <title>{LABELS[i]} · {m.model_key}: {score(m.overall_quality_score)} quality · {milliseconds(m.latency_p50_ms)}</title>
          </g> : null)}
      </svg>
    </div>
    <div className="cmp-scatter-legend cmp3-legend">
      {selected.map((m,i)=><span key={m.model_key}><i className={'cmp3-swatch-' + LABELS[i].toLowerCase()}/>{LABELS[i]} · {m.model_key}</span>)}
      <span><i className="cmp-other-swatch"/>Other models</span>
    </div>
    <p className="cmp-note"><AlertTriangle size={14}/> Observed latency includes effects from runtimes and hardware. This is not a controlled cross-environment performance ranking.</p>
  </>;
}

function ThreeEvidence({ selected, shared, union }: { selected: ThreeModels; shared: number; union: number }) {
  const samePolicy = selected.every(m => m.quality_policy_id === selected[0].quality_policy_id);
  const coverage = shared > 0 && shared === union && selected.every(m => m.quality_coverage_complete);
  const sameRuntime = selected.every(m => m.runtime_key === selected[0].runtime_key && m.execution_profile === selected[0].execution_profile);
  const cpu = selected[0].execution_environment?.cpu_model, machine = selected[0].execution_environment?.machine;
  const sameHardware = Boolean(cpu && machine && selected.every(m => m.execution_environment?.cpu_model === cpu && m.execution_environment?.machine === machine));
  const qualityOk = samePolicy && coverage;
  return <section className="cmp-section">
    <ThreeHeading step="04 / Evidence quality" title="Is the three-way comparison fair?"
      description="Missing dataset scores are excluded from the shared ranking, not treated as zeros."/>
    <div className="cmp-evidence-grid">
      <div className={'cmp-evidence-item' + (qualityOk ? '' : ' cmp-evidence-warning')}>
        {qualityOk ? <CheckCircle2 size={20}/> : <AlertTriangle size={20}/>}
        <div><strong>{qualityOk ? 'Quality coverage aligned' : 'Quality evidence needs review'}</strong>
          <p>{shared} shared scored datasets of {union} present. {samePolicy ? 'Same quality policy.' : 'Different quality policies.'} {coverage ? 'Complete coverage reported by all three.' : 'One or more scores or model coverage flags are missing.'}</p></div>
      </div>
      <div className="cmp-evidence-item"><AlertTriangle size={20}/>
        <div><strong>{sameRuntime && sameHardware ? 'Runtime and hardware labels match' : 'Latency environments differ or are unverified'}</strong>
          <p>{sameRuntime && sameHardware ? 'Reported environment labels match, but workload and system load may differ.' : 'Observed response times must not be presented as intrinsic model speed differences.'}</p>
        </div>
      </div>
    </div>
    <div className="cmp-evidence-stats">
      {selected.map((m,i) => <span key={m.model_key}>{LABELS[i]} · {m.observed_case_count} observed cases</span>)}
      <span>Quality policy: {samePolicy ? selected[0].quality_policy_id : 'mixed'}</span>
    </div>
  </section>;
}

function ThreeTechnical({ selected, shared }: { selected: ThreeModels; shared: ThreeDatasetRow[] }) {
  const rows: Array<[string, (m:DecisionModelSummary)=>string]> = [
    ['Family', m=>m.family??'—'],
    ['Parameters', m=>m.parameters_b == null ? '—' : m.parameters_b + 'B'],
    ['Quantization', m=>m.quantization??'—'],
    ['Artifact', m=>m.artifact_format??'—'],
    ['Deployment', m=>m.deployment],
    ['P50 latency', m=>milliseconds(m.latency_p50_ms)],
    ['P95 latency', m=>milliseconds(m.latency_p95_ms)],
    ['Benchmark failure rate', m=>percent(m.failure_rate)],
    ['Observed cases', m=>String(m.observed_case_count)],
    ['Runtime', m=>m.runtime_key||'—'],
    ['Execution profile', m=>m.execution_profile??'—'],
    ['CPU', m=>m.execution_environment?.cpu_model??'Not recorded'],
    ['Architecture', m=>m.execution_environment?.machine??'Not recorded'],
    ['Peak RSS', m=>bytes(m.resource_summary.process_rss_bytes_peak)],
    ['Temperature', m=>m.generation_parameters?.temperature == null ? '—' : String(m.generation_parameters.temperature)],
    ['Max output tokens', m=>m.generation_parameters?.max_output_tokens == null ? '—' : String(m.generation_parameters.max_output_tokens)],
    ['Seed', m=>m.generation_parameters?.seed == null ? '—' : String(m.generation_parameters.seed)],
    ['Provider cost / 1k cases', m=>providerCostValue(m.provider_cost_status, m.provider_cost_per_1k_cases_usd)],
    ['Cost status', m=>m.provider_cost_status.replaceAll('_',' ')],
  ];
  return <section className="cmp-section cmp-technical">
    <ThreeHeading step="05 / Full evidence" title="Inspect exact results and configuration" description="All three models remain visible in each technical comparison."/>
    <details className="cmp-disclosure">
      <summary><span>Exact dataset scores <small>{shared.length} shared datasets · values, sample counts and leaders</small></span><ChevronDown size={18}/></summary>
      <div className="cmp-exact-wrap"><table className="cmp-exact-table cmp3-technical-table">
        <thead><tr><th>Dataset</th>{LABELS.map(l=><th key={l}>{l} score</th>)}<th>Winning model</th><th>Samples A / B / C</th></tr></thead>
        <tbody>{shared.map(r=><tr key={r.key}><td><strong>{r.dataset}</strong><small>{capabilityLabel(r.capability)}</small></td>
          {r.scores.map((v,i)=><td key={LABELS[i]} className={r.winners.includes(i) ? 'cmp3-tone-'+LABELS[i].toLowerCase() : ''}>{score(v)}</td>)}
          <td>{r.winners.length===1 ? LABELS[r.winners[0]] : 'Tie'}</td><td>{r.samples.join(' / ')}</td>
        </tr>)}</tbody>
      </table></div>
    </details>
    <details className="cmp-disclosure"><summary><span>Model specifications & observed efficiency <small>Hardware, quantization, runtime, latency and price coverage</small></span><ChevronDown size={18}/></summary>
      <div className="cmp-exact-wrap"><table className="cmp-exact-table cmp3-technical-table">
        <thead><tr><th>Metric</th>{selected.map((m,i)=><th key={m.model_key}>{LABELS[i]} · {m.model_key}</th>)}</tr></thead>
        <tbody>{rows.map(([label,format])=><tr key={label}><td>{label}</td>{selected.map(m=><td key={m.model_key}>{format(m)}</td>)}</tr>)}</tbody>
      </table><p className="cmp-note"><Info size={14}/> Local provider cost is N/A, not $0. A missing or partially priced provider value is not treated as a complete comparable cost.</p></div>
    </details>
  </section>;
}

export function CompareThree({ selected, field, datasetRows, preference, onPreferenceChange }: {
  selected: ThreeModels;
  field: DecisionModelSummary[];
  datasetRows: DecisionDatasetSummary[];
  preference: ComparePreference;
  onPreferenceChange: (preference:ComparePreference)=>void;
}) {
  const { shared, unionCount, wins, ties } = sharedThreeDatasets(datasetRows, selected);
  const insight = threeDecisionInsight(selected, preference, shared.length, unionCount);
  return <>
    <section className="cmp-hero cmp3-hero">
      <div className="cmp-hero-top"><div><span className="cmp-eyebrow">01 / Executive decision · three models</span>
        <div className="cmp-model-legend cmp3-model-legend">{selected.map((m,i)=><span key={m.model_key}>
          <i className={'cmp3-swatch-'+LABELS[i].toLowerCase()}/>{LABELS[i]} · {m.model_key}</span>)}</div></div>
        <fieldset className="cmp-preferences"><legend>What matters most?</legend>{PREFERENCES.map(([key,label])=>
          <button type="button" key={key} aria-pressed={key===preference} className={key===preference?'active':''} onClick={()=>onPreferenceChange(key)}>{label}</button>)}</fieldset>
      </div>
      <div className="cmp-hero-statement"><div className="cmp-hero-symbol"><Gauge size={23}/></div>
        <div><h2>{insight.title}</h2><p>{insight.detail}</p></div></div>
      <div className="cmp-hero-strip"><span><CheckCircle2 size={16}/>{shared.length} / {unionCount} common scored datasets</span>
        <span><Layers3 size={16}/>{wins.reduce((a,b)=>a+b,0)} unique task wins · {ties} ties</span>
        <span><Info size={16}/> No fabricated overall weighted score</span></div>
    </section>
    <div className="cmp-metric-grid cmp3-metric-grid">
      <ThreeMetric title="Aggregate quality" icon={<Layers3 size={17}/>}
        values={selected.map(m=>m.overall_quality_score)} format={score} lowerBetter={false} footnote="Higher is better · requires comparable coverage"/>
      <ThreeMetric title="Observed median latency" icon={<Clock3 size={17}/>}
        values={selected.map(m=>m.latency_p50_ms)} format={milliseconds} lowerBetter footnote="Lower is better · execution-dependent P50"/>
      <ThreeMetric title="Benchmark failure rate" icon={<ShieldCheck size={17}/>}
        values={selected.map(m=>m.failure_rate)} format={percent} lowerBetter footnote="Lower is better · observed test failures"/>
    </div>
    <ThreeScoreRows rows={shared} unionCount={unionCount} wins={wins} ties={ties}/>
    <section className="cmp-section">
      <ThreeHeading step="03 / Trade-off landscape" title="Quality versus observed latency"
        description="Three highlighted models, with the rest of the benchmark field for context. Upper-left is preferable only under comparable runtime conditions."/>
      <ThreeScatter field={field} selected={selected}/>
    </section>
    <ThreeEvidence selected={selected} shared={shared.length} union={unionCount}/>
    <ThreeTechnical selected={selected} shared={shared}/>
  </>;
}
