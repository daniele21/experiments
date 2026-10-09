import { AlertTriangle, CheckCircle2, ChevronDown, Cpu, HardDrive, Info } from 'lucide-react';
import type { DecisionModelSummary } from '../types';
import { bytes, milliseconds, score } from '../utils';
import { getHardwareComparability, peakAttribution, peakRss } from './hardwareEvidence';
import './hardwareMemory.css';

const LETTERS = ['A', 'B', 'C'] as const;
const GIB = 1024 ** 3;
function readableBytes(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) || value < 0 ? '—' : bytes(value);
}

function MemoryCard({ model, index, max }: { model: DecisionModelSummary; index: number; max: number }) {
  const peak = peakRss(model);
  const attribution = peakAttribution(model);
  const host = attribution.environment;
  const hasPeakHost = attribution.provenance === 'recorded-peak-run' || attribution.provenance === 'single-run';
  const resource = model.resource_summary;
  const label = LETTERS[index];
  return <article className="mem-card">
    <div className="mem-card-heading">
      <span className={'mem-letter mem-letter-' + label.toLowerCase()}>{label}</span>
      <strong title={model.model_key}>{model.model_key}</strong>
      <span className="mem-deployment">{model.deployment}</span>
    </div>
    <div className="mem-primary-label">Peak process RAM (RSS)</div>
    <div className="mem-primary">{readableBytes(peak)}</div>
    <div className="mem-bar-track" role="img" aria-label={'Peak process RAM: ' + readableBytes(peak)}>
      {peak != null && <i className={'mem-bar-' + label.toLowerCase()} style={{ width: (peak / max * 100) + '%' }}/>}
    </div>
    <dl className="mem-card-facts">
      <div><dt>Test host / CPU</dt><dd>{host?.cpu_model || 'Not recorded'}</dd></div>
      <div><dt>Architecture</dt><dd>{[host?.system, host?.machine].filter(Boolean).join(' · ') || '—'}</dd></div>
      <div><dt>Host memory</dt><dd>{readableBytes(host?.total_memory_bytes)}</dd></div>
      <div><dt>Mean process RSS</dt><dd>{readableBytes(resource?.process_rss_bytes_avg)}</dd></div>
    </dl>
    <div className="mem-source">
      {hasPeakHost ? <CheckCircle2 size={14}/> : <AlertTriangle size={14}/>}
      <span>{attribution.provenance === 'recorded-peak-run'
        ? 'Device linked to measured peak run'
        : attribution.provenance === 'single-run'
          ? 'Device linked to the sole current run'
          : attribution.provenance === 'latest-only'
            ? 'Latest test device; peak-run device unverified'
            : 'Peak not measured; latest test device shown'}</span>
    </div>
  </article>;
}

function QualityMemoryPlot({ selected, field }: {
  selected: DecisionModelSummary[];
  field: DecisionModelSummary[];
}) {
  const fieldRows = field.filter(m => peakRss(m) != null && m.overall_quality_score != null &&
    Number.isFinite(m.overall_quality_score));
  if (fieldRows.length < 2) return <p className="mem-empty">Quality × RAM requires at least two models with both quality and measured process RSS.</p>;
  const allPeaks = fieldRows.map(m => peakRss(m)! / GIB);
  const maxX = Math.max(1, Math.max(...allPeaks) * 1.13);
  const ys = fieldRows.map(m => m.overall_quality_score!);
  const minY = Math.max(0,Math.min(...ys)-10);
  const maxY = Math.min(100,Math.max(...ys)+10);
  const x = (peak: number) => 75 + (peak/GIB/maxX)*755;
  const y = (quality: number) => 244 - (quality-minY)/Math.max(1,maxY-minY)*203;
  const keys = new Set(selected.map(m=>m.model_key));
  return <div className="mem-chart-frame">
    <svg className="mem-chart" viewBox="0 0 900 307" role="img" aria-label="Quality versus observed peak process RSS. Selected models highlighted with letters. Lower peak memory and higher quality are preferable.">
      {Array.from({length:5},(_,i)=>i).map(i => <g key={i}>
        <line className="mem-grid" x1={75+755*i/4} x2={75+755*i/4} y1="39" y2="244"/>
        <line className="mem-grid" x1="75" x2="830" y1={244-203*i/4} y2={244-203*i/4}/>
        <text className="mem-axis" x={75+755*i/4} y="267" textAnchor="middle">{(maxX*i/4).toFixed(1)}</text>
        <text className="mem-axis" x="64" y={248-203*i/4} textAnchor="end">{(minY+(maxY-minY)*i/4).toFixed(0)}</text>
      </g>)}
      <text className="mem-axis-title" textAnchor="middle" x="455" y="296">Peak process RSS (GiB) · lower is better ←</text>
      <text className="mem-axis-title" transform="translate(18,145) rotate(-90)" textAnchor="middle">Quality score ↑</text>
      {fieldRows.filter(m=>!keys.has(m.model_key)).map(m=><circle key={m.model_signature} cx={x(peakRss(m)!)} cy={y(m.overall_quality_score!)} r="5" className="mem-other-point">
        <title>{m.model_key}: quality {score(m.overall_quality_score)} / peak RSS {readableBytes(peakRss(m))}</title>
      </circle>)}
      {selected.map((m,i)=> peakRss(m) != null && m.overall_quality_score != null &&
        Number.isFinite(m.overall_quality_score)
        ? <g key={m.model_key}>
          <circle cx={x(peakRss(m)!)} cy={y(m.overall_quality_score!)} r="12" className={'mem-scatter-'+LETTERS[i].toLowerCase()}/>
          <text x={x(peakRss(m)!)} y={y(m.overall_quality_score!)+4} textAnchor="middle" className="mem-scatter-letter">{LETTERS[i]}</text>
          <title>{LETTERS[i]} · {m.model_key}: quality {score(m.overall_quality_score)} / peak RSS {readableBytes(peakRss(m))}</title>
        </g> : null)}
    </svg>
  </div>;
}

export function HardwareMemoryComparison({ selected, field }: {
  selected: DecisionModelSummary[];
  field: DecisionModelSummary[];
}) {
  const memoryModels = selected.filter(m=>peakRss(m)!=null);
  const comparison = getHardwareComparability(selected);
  const maxPeak = Math.max(1,...memoryModels.map(m=>peakRss(m)!));
  const noMemoryCount = selected.length - memoryModels.length;
  return <section className="cmp-section mem-section">
    <div className="cmp-section-heading mem-section-heading">
      <div><span className="cmp-eyebrow">Hardware & resource efficiency</span><h2>How much memory does each model need?</h2>
        <p>Measured process RSS and the device used for the peak run, not model file size or estimated system RAM consumption.</p>
      </div>
      <span className={'mem-confidence mem-confidence-' + comparison.status}>
        {comparison.status === 'matched' ? <CheckCircle2 size={16}/> : <AlertTriangle size={16}/>}
        {comparison.status === 'matched' ? 'Host hardware matched' : comparison.status === 'mismatch' ? 'Different hardware' : 'Comparison limited'}
      </span>
    </div>
    <div className={'mem-card-grid mem-card-grid-'+selected.length}>
      {selected.map((m,i)=><MemoryCard key={m.model_key} model={m} index={i} max={maxPeak}/>)}
    </div>
    <div className="mem-evidence-line">
      <Info size={17}/><span>{comparison.detail}
        {noMemoryCount > 0 ? ' Memory measurements are unavailable for ' + noMemoryCount + ' selected model(s).' : ''}
      </span>
    </div>
    <div className="mem-chart-heading">
      <div><h3>Quality × Peak RAM</h3><p>Smaller process footprint (left) and higher quality (top). Other measured models provide context.</p></div>
      <span className="mem-chart-key"><i className="mem-other-swatch"/>Other models</span>
    </div>
    <QualityMemoryPlot selected={selected} field={field}/>
    <p className="cmp-note"><AlertTriangle size={14}/>
      RSS is sampled process-resident memory, not complete model memory or unified-memory/Metal allocation.
      The peak is a maximum across selected capability runs, while aggregate quality may combine multiple runs.
      Use the linked peak-run host and scope before judging efficiency.</p>
    <details className="cmp-disclosure mem-details">
      <summary><span>Resource measurement details <small>Sampling, scope, run provenance and available memory</small></span><ChevronDown size={18}/></summary>
      <div className="cmp-exact-wrap">
        <table className="cmp-exact-table mem-evidence-table">
          <thead><tr><th>Measurement</th>{selected.map((m,i)=><th key={m.model_key}>{LETTERS[i]} · {m.model_key}</th>)}</tr></thead>
          <tbody>
            {([
              ['Measured peak RSS','process_rss_bytes_peak'],
              ['Mean RSS across resource summaries','process_rss_bytes_avg'],
              ['Peak accelerator memory','accelerator_memory_bytes_peak'],
              ['Lowest system-available memory','system_available_memory_bytes_min'],
            ] as const).map(([title,key])=><tr key={key}><td>{title}</td>{selected.map(m=><td key={m.model_key}>{readableBytes(m.resource_summary?.[key])}</td>)}</tr>)}
            <tr><td>Memory telemetry scope</td>{selected.map(m=><td key={m.model_key}>{m.resource_summary?.scope || 'Not recorded'}</td>)}</tr>
            <tr><td>Sampling source</td>{selected.map(m=><td key={m.model_key}>{m.resource_summary?.source || 'Not recorded'}</td>)}</tr>
            <tr><td>Sample count / failures</td>{selected.map(m=><td key={m.model_key}>{m.resource_summary?.sample_count == null ? '—' : m.resource_summary.sample_count} / {m.resource_summary?.sampling_error_count ?? '—'}</td>)}</tr>
            <tr><td>Peak run ID</td>{selected.map(m=><td key={m.model_key}>{peakAttribution(m).peakRunId || 'Not recorded'}</td>)}</tr>
            <tr><td>Host for peak</td>{selected.map(m=><td key={m.model_key}>{peakAttribution(m).provenance === 'latest-only' ? 'Unverified' : peakAttribution(m).environment?.cpu_model || 'Not recorded'}</td>)}</tr>
            <tr><td>Device RAM (host capacity)</td>{selected.map(m=><td key={m.model_key}>{readableBytes(peakAttribution(m).environment?.total_memory_bytes)}</td>)}</tr>
            <tr><td>Observed median latency</td>{selected.map(m=><td key={m.model_key}>{milliseconds(m.latency_p50_ms)}</td>)}</tr>
            <tr><td>Current benchmark runs</td>{selected.map(m=><td key={m.model_key}>{m.current_run_ids?.length ?? 0}</td>)}</tr>
          </tbody>
        </table>
      </div>
    </details>
    <div className="mem-footnote"><Cpu size={15}/><span>Device labels come from recorded execution environments. On Apple Silicon, RSS alone is not a complete measure of unified-memory pressure.</span><HardDrive size={15}/></div>
  </section>;
}
