import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, Clock3, Gauge, GitCompareArrows, Info, Layers3, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { overview } from '../data';
import { navigate } from '../router';
import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { bytes, capabilityLabel, milliseconds, percent, providerCostValue, score } from '../utils';
import { MethodologyAccordion } from './DecisionComponents';
import { ModelParametersComparison } from './ModelParameters';
import { PageHeader } from './Shell';
import { CompareThree } from './CompareThree';
import './compareDecision.css';

type Preference = 'balanced' | 'quality' | 'speed' | 'reliability';
type Pair = { key: string; capability: string; dataset: string; a: number; b: number; delta: number; samplesA: number; samplesB: number };
const TIE_EPSILON = 0.05;

function pairDatasets(rows: DecisionDatasetSummary[], a: DecisionModelSummary, b: DecisionModelSummary) {
  const fromA = rows.filter((row) => row.model_key === a.model_key);
  const fromB = rows.filter((row) => row.model_key === b.model_key);
  const bByKey = new Map(fromB.map((row) => [row.capability_id + '::' + row.dataset_id, row]));
  const pairs: Pair[] = fromA.flatMap((row) => {
    const key = row.capability_id + '::' + row.dataset_id;
    const other = bByKey.get(key);
    if (row.normalized_quality_score == null || other?.normalized_quality_score == null) return [];
    return [{
      key, capability: row.capability_id, dataset: row.dataset_id,
      a: row.normalized_quality_score, b: other.normalized_quality_score,
      delta: row.normalized_quality_score - other.normalized_quality_score,
      samplesA: row.sample_count, samplesB: other.sample_count,
    }];
  });
  const union = new Set([...fromA, ...fromB].map((row) => row.capability_id + '::' + row.dataset_id)).size;
  pairs.sort((x, y) => Math.abs(y.delta) - Math.abs(x.delta));
  return { pairs, union };
}

function getWinner(a: number | null | undefined, b: number | null | undefined, lower = false): 'a' | 'b' | null {
  if (a == null || b == null || Math.abs(a - b) < 1e-9) return null;
  return (lower ? a < b : a > b) ? 'a' : 'b';
}

function conciseModel(name: string): string {
  return name.length > 24 ? name.slice(0, 22) + '…' : name;
}

function currentQuery(name: string): string | null {
  const url = new URLSearchParams(window.location.search);
  const direct = url.get(name);
  if (direct) return direct;
  if (window.location.hash.includes('?')) return new URLSearchParams(window.location.hash.split('?')[1]).get(name);
  return null;
}
function compareHref(a: string, b: string, c?: string) {
  const params = new URLSearchParams({ modelA: a, modelB: b });
  if (c) params.set('modelC', c);
  return '/compare?' + params.toString();
}

function guidance(preference: Preference, a: DecisionModelSummary, b: DecisionModelSummary) {
  const q = getWinner(a.overall_quality_score, b.overall_quality_score);
  const s = getWinner(a.latency_p50_ms, b.latency_p50_ms, true);
  const r = getWinner(a.failure_rate, b.failure_rate, true);
  const name = (which: 'a' | 'b') => which === 'a' ? a.model_key : b.model_key;
  if (preference === 'quality') return q
    ? { title: name(q) + ' leads on aggregate quality', detail: 'This preference prioritizes the observed benchmark score. Check task-level differences and coverage before choosing.' }
    : { title: 'No measured quality leader', detail: 'The observed aggregate quality values are equal or unavailable.' };
  if (preference === 'speed') return s
    ? { title: name(s) + ' has lower observed latency', detail: 'This is a runtime-specific P50 result, not an intrinsic model-speed guarantee. Compare the execution environments before deployment.' }
    : { title: 'No measured speed leader', detail: 'Comparable observed P50 latency values are not available or are equal.' };
  if (preference === 'reliability') return r
    ? { title: name(r) + ' has fewer observed failures', detail: 'Failure rates come from benchmark execution. Inspect sample counts and failure types before generalizing to production reliability.' }
    : { title: 'No measured reliability leader', detail: 'Observed failure rates are equal or unavailable.' };
  if (q && s && r && q === s && q === r) {
    return { title: name(q) + ' leads across the three observed metrics', detail: 'Quality, P50 latency and benchmark failure rate favor the same model. The speed comparison remains environment-specific.' };
  }
  if (q && s && q !== s) {
    return { title: 'A real trade-off: quality versus responsiveness', detail: name(q) + ' leads on aggregate quality; ' + name(s) + ' has lower observed median latency. Dataset-specific priorities should decide.' };
  }
  if (q && r && q !== r) {
    return { title: 'A real trade-off: quality versus reliability', detail: name(q) + ' leads on aggregate quality; ' + name(r) + ' has fewer observed failures.' };
  }
  return { title: 'No universal winner from the available evidence', detail: 'Compare the task-level results, observed efficiency and evidence coverage rather than relying on a single aggregate number.' };
}

function SummaryMetric({
  title, icon, a, b, direction, formatter, kind,
}: {
  title: string; icon: 'quality' | 'speed' | 'reliability';
  a: number | null | undefined; b: number | null | undefined;
  direction: 'higher' | 'lower'; formatter: (n: number | null | undefined) => string;
  kind: 'quality' | 'latency' | 'failure';
}) {
  const winner = getWinner(a, b, direction === 'lower');
  const both = a != null && b != null;
  const ratio = both && Math.min(a, b) > 0 ? Math.max(a, b) / Math.min(a, b) : null;
  const difference = both ? Math.abs(a - b) : null;
  let headline = '—';
  if (difference != null) {
    if (kind === 'quality') headline = difference.toFixed(1) + ' pts';
    else if (ratio != null && ratio >= 1.05) headline = ratio.toFixed(1) + '×';
    else if (kind === 'failure') headline = (difference * 100).toFixed(1) + ' pp';
    else headline = milliseconds(difference);
  }
  const max = Math.max(a ?? 0, b ?? 0, 0.0001);
  const Icon = icon === 'quality' ? Layers3 : icon === 'speed' ? Clock3 : ShieldCheck;
  return (
    <article className="cmp-metric-card">
      <div className="cmp-metric-title"><Icon size={17}/><span>{title}</span></div>
      <div className={'cmp-metric-big ' + (winner ? 'cmp-tone-' + winner : '')}>{headline}</div>
      <div className="cmp-metric-verdict">{winner ? 'Model ' + winner.toUpperCase() + ' leads' : both ? 'Equal observed result' : 'Insufficient data'}</div>
      <div className="cmp-two-bars" aria-label={'Model A: ' + formatter(a) + ', Model B: ' + formatter(b)}>
        <div><span>A</span><div className="cmp-bar-track"><i className="cmp-bar-a" style={{ width: (Math.max(0, a ?? 0) / max) * 100 + '%' }}/></div><b>{formatter(a)}</b></div>
        <div><span>B</span><div className="cmp-bar-track"><i className="cmp-bar-b" style={{ width: (Math.max(0, b ?? 0) / max) * 100 + '%' }}/></div><b>{formatter(b)}</b></div>
      </div>
      <div className="cmp-metric-footnote">{kind === 'quality' ? 'Higher is better' : kind === 'latency' ? 'Lower is better · observed P50' : 'Lower is better · benchmark failures'}</div>
    </article>
  );
}

function DeltaRow({ pair, scale }: { pair: Pair; scale: number }) {
  const win = pair.delta > TIE_EPSILON ? 'a' : pair.delta < -TIE_EPSILON ? 'b' : 'tie';
  const width = Math.abs(pair.delta) <= TIE_EPSILON ? 0 : Math.max(1, Math.min(100, Math.abs(pair.delta) / scale * 100));
  return (
    <div className="cmp-delta-row">
      <div className="cmp-dataset-name"><strong title={pair.dataset}>{pair.dataset}</strong><small>{capabilityLabel(pair.capability)}</small></div>
      <div className="cmp-delta-plot" role="img" aria-label={'A ' + score(pair.a) + ', B ' + score(pair.b) + ', delta ' + (pair.delta > 0 ? '+' : '') + pair.delta.toFixed(1)}>
        <div className="cmp-delta-half cmp-delta-left">{win === 'a' && <i style={{ width: width + '%' }}/>}</div>
        <div className="cmp-delta-zero"/>
        <div className="cmp-delta-half cmp-delta-right">{win === 'b' && <i style={{ width: width + '%' }}/>}</div>
      </div>
      <div className={'cmp-delta-value cmp-tone-' + win}>{win === 'tie' ? '≈ 0' : (win === 'a' ? 'A +' : 'B +') + Math.abs(pair.delta).toFixed(1)}</div>
      <div className="cmp-delta-raw">A {score(pair.a)} <span>·</span> B {score(pair.b)}</div>
    </div>
  );
}

function DatasetEvidence({ pairs, union }: { pairs: Pair[]; union: number }) {
  const aWins = pairs.filter((row) => row.delta > TIE_EPSILON).length;
  const bWins = pairs.filter((row) => row.delta < -TIE_EPSILON).length;
  const ties = pairs.length - aWins - bWins;
  const outlier = pairs.length > 2 && Math.abs(pairs[0].delta) >= 15 &&
    Math.abs(pairs[0].delta) >= 3 * Math.max(Math.abs(pairs[1].delta), 0.01) ? pairs[0] : null;
  const rows = outlier ? pairs.slice(1) : pairs;
  const scale = Math.max(...rows.map((row) => Math.abs(row.delta)), 1);
  return (
    <section className="cmp-section">
      <div className="cmp-section-heading">
        <div><span className="cmp-eyebrow">02 / Task-level evidence</span><h2>Where does each model win?</h2><p>Every bar represents the actual quality-score gap. Blue favors A; teal favors B.</p></div>
        <div className="cmp-win-summary"><span className="cmp-tone-a">{aWins} A wins</span><span className="cmp-tone-b">{bWins} B wins</span><span>{ties} ties</span></div>
      </div>
      {outlier && (
        <div className="cmp-outlier">
          <div><div className="cmp-eyebrow">Largest observed gap · inspect individual cases</div><strong>{outlier.dataset}</strong><span>{capabilityLabel(outlier.capability)} · A {score(outlier.a)} vs B {score(outlier.b)}</span></div>
          <div className={outlier.delta > 0 ? 'cmp-tone-a' : 'cmp-tone-b'}><b>{outlier.delta > 0 ? 'A +' : 'B +'}{Math.abs(outlier.delta).toFixed(1)}</b><span>quality points</span></div>
        </div>
      )}
      {rows.length ? (
        <>
          <div className="cmp-delta-columns"><span>Dataset</span><div><span>← A advantage</span><span>B advantage →</span></div><span>Gap</span></div>
          <div className="cmp-delta-list">{rows.map((pair) => <DeltaRow key={pair.key} pair={pair} scale={scale}/>)}</div>
          <p className="cmp-note">Common zero-centered scale across {rows.length} displayed rows (largest magnitude {scale.toFixed(1)} points). {outlier ? 'The extreme outlier is shown separately to preserve the smaller differences.' : ''} Paired evidence: {pairs.length} of {union} dataset/capability combinations.</p>
        </>
      ) : <p className="cmp-note">No comparable dataset scores for this model pair.</p>}
    </section>
  );
}

function Scatter({ models, a, b }: { models: DecisionModelSummary[]; a: DecisionModelSummary; b: DecisionModelSummary }) {
  const valid = models.filter((model) => model.latency_p50_ms != null && model.latency_p50_ms > 0 && model.overall_quality_score != null);
  if (valid.length < 2) return <div className="cmp-note">Not enough models with both quality and latency measurements.</div>;
  const logs = valid.map((model) => Math.log10(model.latency_p50_ms!));
  const lo = Math.min(...logs);
  const hi = Math.max(...logs);
  const pad = Math.max((hi - lo) * 0.12, 0.15);
  const lowX = lo - pad, highX = hi + pad;
  const ys = valid.map((model) => model.overall_quality_score!);
  const lowY = Math.max(0, Math.min(...ys) - 12), highY = Math.min(100, Math.max(...ys) + 12);
  const x = (v: number) => 78 + (Math.log10(v) - lowX) / (highX - lowX) * 756;
  const y = (v: number) => 247 - (v - lowY) / Math.max(1, highY - lowY) * 207;
  const ticks = Array.from({ length: 5 }, (_, i) => i);
  return (
    <svg viewBox="0 0 900 310" className="cmp-scatter" role="img" aria-label="Observed quality versus median latency, selected models highlighted">
      {ticks.map((tick) => {
        const xp = 78 + tick / 4 * 756;
        const yp = 247 - tick / 4 * 207;
        return (
          <g key={tick}>
            <line x1={xp} y1="35" x2={xp} y2="247" className="cmp-grid-line"/>
            <line x1="78" y1={yp} x2="834" y2={yp} className="cmp-grid-line"/>
            <text x={xp} y="266" textAnchor="middle" className="cmp-axis-label">{milliseconds(10 ** (lowX + tick / 4 * (highX - lowX)))}</text>
            <text x="66" y={yp + 4} textAnchor="end" className="cmp-axis-label">{(lowY + tick / 4 * (highY - lowY)).toFixed(0)}</text>
          </g>
        );
      })}
      <text x="456" y="296" textAnchor="middle" className="cmp-axis-title">Observed P50 latency · log scale · lower is better → left</text>
      <text transform="translate(17 141) rotate(-90)" textAnchor="middle" className="cmp-axis-title">Quality score ↑</text>
      {valid.filter((m) => m.model_key !== a.model_key && m.model_key !== b.model_key).map((model) =>
        <circle key={model.model_signature} cx={x(model.latency_p50_ms!)} cy={y(model.overall_quality_score!)} r="5" className="cmp-other-point"><title>{model.model_key + ': quality ' + score(model.overall_quality_score) + ', P50 ' + milliseconds(model.latency_p50_ms)}</title></circle>,
      )}
      {[a, b].filter((model) => model.latency_p50_ms != null && model.latency_p50_ms > 0 && model.overall_quality_score != null).map((model) => {
        const isA = model.model_key === a.model_key;
        const xp = x(model.latency_p50_ms!), yp = y(model.overall_quality_score!);
        return (
          <g key={model.model_signature}>
            <circle cx={xp} cy={yp} r="12" className={isA ? 'cmp-selected-point-a' : 'cmp-selected-point-b'}/>
            <text x={xp > 680 ? xp - 16 : xp + 16} y={yp - 13} textAnchor={xp > 680 ? 'end' : 'start'} className={isA ? 'cmp-point-label-a' : 'cmp-point-label-b'}>{(isA ? 'A · ' : 'B · ') + conciseModel(model.model_key)}</text>
            <title>{model.model_key + ': quality ' + score(model.overall_quality_score) + ', P50 ' + milliseconds(model.latency_p50_ms)}</title>
          </g>
        );
      })}
    </svg>
  );
}

function EvidenceContext({ a, b, shared, union }: { a: DecisionModelSummary; b: DecisionModelSummary; shared: number; union: number }) {
  const samePolicy = a.quality_policy_id === b.quality_policy_id;
  const envA = a.execution_environment, envB = b.execution_environment;
  const hardwareMatches = Boolean(envA?.machine && envB?.machine && envA.machine === envB.machine && envA.cpu_model && envA.cpu_model === envB.cpu_model);
  const runtimeMatches = a.runtime_key === b.runtime_key && a.execution_profile === b.execution_profile;
  const complete = a.quality_coverage_complete && b.quality_coverage_complete && shared === union;
  return (
    <section className="cmp-section cmp-evidence">
      <div className="cmp-section-heading"><div><span className="cmp-eyebrow">04 / Interpretation guardrails</span><h2>How much can we trust the comparison?</h2><p>Evidence coverage and execution conditions affect what can be concluded.</p></div></div>
      <div className="cmp-evidence-grid">
        <div className={"cmp-evidence-item" + (samePolicy && shared > 0 ? "" : " cmp-evidence-warning")}>{samePolicy && shared > 0 ? <CheckCircle2 size={20}/> : <AlertTriangle size={20}/>}<div><strong>{samePolicy && shared > 0 ? 'Shared quality policy' : 'Quality comparability limited'}</strong><p>{shared} shared scored datasets out of {union}. {complete && samePolicy ? 'Both models report complete quality coverage.' : 'Inspect incomplete or unmatched coverage before interpreting the aggregate gap.'}</p></div></div>
        <div className="cmp-evidence-item"><AlertTriangle size={20}/><div><strong>{runtimeMatches && hardwareMatches ? 'Matching reported runtime and hardware' : 'Latency is environment-specific'}</strong><p>{runtimeMatches && hardwareMatches ? 'The recorded execution labels match; configuration and load can still differ.' : 'Different or unverified hardware/runtime context: do not interpret this speed ratio as a controlled model-only comparison.'}</p></div></div>
      </div>
      <div className="cmp-evidence-stats">
        <span>A · {a.observed_case_count} observed cases</span><span>B · {b.observed_case_count} observed cases</span>
        <span>Quality policy: {samePolicy ? a.quality_policy_id : 'different policies'}</span>
      </div>
    </section>
  );
}

export function CompareDecision() {
  const models = [...(overview.decision?.model_summaries ?? [])].sort((a, b) => (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1));
  const datasetRows = overview.decision?.dataset_summaries ?? [];
  const [aKey, setAKey] = useState(() => currentQuery('modelA') ?? models[0]?.model_key ?? '');
  const [bKey, setBKey] = useState(() => currentQuery('modelB') ?? models.find((model) => model.model_key !== aKey && model.deployment === 'local')?.model_key ?? models.find((model) => model.model_key !== aKey)?.model_key ?? '');
  const [cKey, setCKey] = useState(() => currentQuery('modelC') ?? '');
  const [preference, setPreference] = useState<Preference>('balanced');
  useEffect(() => {
    const syncSelectionFromUrl = () => {
      const nextA = currentQuery('modelA');
      const nextB = currentQuery('modelB');
      if (nextA) setAKey(nextA);
      if (nextB) setBKey(nextB);
      setCKey(currentQuery('modelC') ?? '');
    };
    window.addEventListener('popstate', syncSelectionFromUrl);
    window.addEventListener('hashchange', syncSelectionFromUrl);
    return () => {
      window.removeEventListener('popstate', syncSelectionFromUrl);
      window.removeEventListener('hashchange', syncSelectionFromUrl);
    };
  }, []);

  const a = models.find((model) => model.model_key === aKey) ?? models[0];
  const b = models.find((model) => model.model_key === bKey && model.model_key !== a?.model_key) ?? models.find((model) => model.model_key !== a?.model_key);
  const c = cKey ? models.find(model => model.model_key === cKey && model.model_key !== a?.model_key && model.model_key !== b?.model_key)
    ?? models.find(model => model.model_key !== a?.model_key && model.model_key !== b?.model_key) : undefined;
  const freeThird = (first: string, second: string, preferred: string) =>
    preferred && preferred !== first && preferred !== second ? preferred :
      models.find(model => model.model_key !== first && model.model_key !== second)?.model_key ?? '';
  const changeA = (key: string) => {
    const nextB = key === b?.model_key ? a?.model_key ?? '' : b?.model_key ?? '';
    const nextC = cKey ? freeThird(key, nextB, cKey) : '';
    setAKey(key); setBKey(nextB); setCKey(nextC);
    navigate(compareHref(key, nextB, nextC));
  };
  const changeB = (key: string) => {
    const nextC = cKey ? freeThird(a?.model_key ?? '', key, cKey) : '';
    setBKey(key); setCKey(nextC);
    navigate(compareHref(a?.model_key ?? '', key, nextC));
  };
  const changeC = (key: string) => {
    setCKey(key);
    navigate(compareHref(a?.model_key ?? '', b?.model_key ?? '', key));
  };
  const setMode = (three: boolean) => {
    const nextC = three ? freeThird(a?.model_key ?? '', b?.model_key ?? '', cKey) : '';
    setCKey(nextC);
    navigate(compareHref(a?.model_key ?? '', b?.model_key ?? '', nextC));
  };

  return (
    <div className="compare-v2">
      <PageHeader eyebrow="Decision intelligence" title="Compare models"
        description="Choose based on trade-offs, task-level strengths and the evidence behind each result."
        actions={<div className={'cmp-selectors' + (c ? ' cmp3-selectors' : '')}>
          <div className="cmp-model-count" role="group" aria-label="Number of models to compare">
            <button type="button" className={!c ? 'active' : ''} aria-pressed={!c} onClick={() => setMode(false)}>2 models</button>
            <button type="button" className={c ? 'active' : ''} aria-pressed={Boolean(c)} disabled={models.length < 3} onClick={() => setMode(true)}>3 models</button>
          </div>
          <label><span>Model A</span><select aria-label="Model A" value={a?.model_key ?? ''} onChange={(event) => changeA(event.target.value)}>{models.map((model) => <option key={model.model_key} value={model.model_key}>{model.model_key}</option>)}</select></label>
          <span>vs</span>
          <label><span>Model B</span><select aria-label="Model B" value={b?.model_key ?? ''} onChange={(event) => changeB(event.target.value)}>{models.filter((model) => model.model_key !== a?.model_key).map((model) => <option key={model.model_key} value={model.model_key}>{model.model_key}</option>)}</select></label>
          {c && <><span>vs</span><label><span>Model C</span><select aria-label="Model C" value={c.model_key} onChange={(event) => changeC(event.target.value)}>{models.filter(model => model.model_key !== a?.model_key && model.model_key !== b?.model_key).map(model => <option key={model.model_key} value={model.model_key}>{model.model_key}</option>)}</select></label>
            <button type="button" className="cmp-remove-third" aria-label="Remove third model" onClick={() => setMode(false)}>Remove C ×</button></>}
        </div>}
      />
      {a && b ? c
        ? <CompareThree selected={[a, b, c]} field={models} datasetRows={datasetRows} preference={preference} onPreferenceChange={setPreference}/>
        : (() => {
        const { pairs, union } = pairDatasets(datasetRows, a, b);
        const insight = guidance(preference, a, b);
        const qualityDelta = a.overall_quality_score != null && b.overall_quality_score != null ? a.overall_quality_score - b.overall_quality_score : null;
        const aCost = a.provider_cost_status === 'complete' ? a.provider_cost_per_1k_cases_usd : null;
        const bCost = b.provider_cost_status === 'complete' ? b.provider_cost_per_1k_cases_usd : null;
        return <>
          <section className="cmp-hero">
            <div className="cmp-hero-top">
              <div><span className="cmp-eyebrow">01 / Executive decision</span><div className="cmp-model-legend"><span><i className="cmp-swatch-a"/>A · {a.model_key}</span><span><i className="cmp-swatch-b"/>B · {b.model_key}</span></div></div>
              <fieldset className="cmp-preferences"><legend>What matters most?</legend>{([
                ['balanced', 'Balanced'], ['quality', 'Quality'], ['speed', 'Speed'], ['reliability', 'Reliability'],
              ] as const).map(([key, label]) => <button type="button" key={key} aria-pressed={preference === key} className={preference === key ? 'active' : ''} onClick={() => setPreference(key)}>{label}</button>)}</fieldset>
            </div>
            <div className="cmp-hero-statement"><div className="cmp-hero-symbol"><GitCompareArrows size={23}/></div><div><h2>{insight.title}</h2><p>{insight.detail}</p></div></div>
            <div className="cmp-hero-strip"><span><CheckCircle2 size={16}/> {pairs.length} paired scored datasets</span><span><Gauge size={16}/> {qualityDelta == null ? 'Quality gap unavailable' : (qualityDelta > 0 ? 'A +' : qualityDelta < 0 ? 'B +' : 'Equal quality ') + Math.abs(qualityDelta).toFixed(1) + ' pts'}</span><span><Info size={16}/> Latency is observed, not normalized</span></div>
          </section>

          <div className="cmp-metric-grid">
            <SummaryMetric title="Aggregate quality" icon="quality" a={a.overall_quality_score} b={b.overall_quality_score} direction="higher" formatter={score} kind="quality"/>
            <SummaryMetric title="Median response latency" icon="speed" a={a.latency_p50_ms} b={b.latency_p50_ms} direction="lower" formatter={milliseconds} kind="latency"/>
            <SummaryMetric title="Observed failure rate" icon="reliability" a={a.failure_rate} b={b.failure_rate} direction="lower" formatter={percent} kind="failure"/>
          </div>

          <DatasetEvidence pairs={pairs} union={union}/>

          <section className="cmp-section">
            <div className="cmp-section-heading"><div><span className="cmp-eyebrow">03 / Efficiency trade-off</span><h2>Is the quality improvement worth the latency?</h2><p>The selected models stand out against the wider benchmark field. Upper-left is preferable within a comparable execution context.</p></div></div>
            <div className="cmp-scatter-frame"><Scatter models={models} a={a} b={b}/></div>
            <div className="cmp-scatter-legend"><span><i className="cmp-swatch-a"/>Model A</span><span><i className="cmp-swatch-b"/>Model B</span><span><i className="cmp-other-swatch"/>Other tested models</span></div>
            <p className="cmp-note"><AlertTriangle size={14}/> The plot shows observed latency. Different runtime or hardware conditions may make points unsuitable for direct efficiency ranking.</p>
          </section>

          <EvidenceContext a={a} b={b} shared={pairs.length} union={union}/>

          <section className="cmp-section cmp-technical">
            <div className="cmp-section-heading"><div><span className="cmp-eyebrow">05 / Drill-down</span><h2>Explore the underlying numbers</h2><p>Detailed evidence is available without overwhelming the executive view.</p></div></div>
            <details className="cmp-disclosure"><summary><span>Exact dataset scores <small>{pairs.length} paired comparisons</small></span><ChevronDown size={18}/></summary>
              <div className="cmp-exact-wrap"><table className="cmp-exact-table"><thead><tr><th>Dataset / capability</th><th>Model A</th><th>Model B</th><th>A − B</th><th>Cases A / B</th></tr></thead><tbody>{pairs.map((row) => <tr key={row.key}><td><strong>{row.dataset}</strong><small>{capabilityLabel(row.capability)}</small></td><td>{score(row.a)}</td><td>{score(row.b)}</td><td className={row.delta > TIE_EPSILON ? 'cmp-tone-a' : row.delta < -TIE_EPSILON ? 'cmp-tone-b' : ''}>{row.delta > 0 ? '+' : ''}{row.delta.toFixed(1)}</td><td>{row.samplesA} / {row.samplesB}</td></tr>)}</tbody></table></div>
            </details>
            <details className="cmp-disclosure"><summary><span>Cost and pricing availability <small>Pricing is not model-runtime efficiency</small></span><ChevronDown size={18}/></summary>
              <div className="cmp-cost-inner">
                {aCost != null && bCost != null ? <div className="cmp-priced-pair"><div><strong>A · {a.model_key}</strong><b>{providerCostValue(a.provider_cost_status, aCost)}</b></div><div><strong>B · {b.model_key}</strong><b>{providerCostValue(b.provider_cost_status, bCost)}</b></div><p>Known provider cost per 1,000 benchmark cases. It is not the cost of running local hardware.</p></div> : <p><Info size={17}/> A like-for-like provider price comparison is unavailable. A: {providerCostValue(a.provider_cost_status, aCost)} ({a.provider_cost_status.replaceAll('_',' ')}); B: {providerCostValue(b.provider_cost_status, bCost)} ({b.provider_cost_status.replaceAll('_',' ')}). No artificial zero cost is assumed for local models.</p>}
              </div>
            </details>
            <details className="cmp-disclosure"><summary><span>Tail latency and runtime environment <small>P95, hardware and measured memory</small></span><ChevronDown size={18}/></summary>
              <div className="cmp-exact-wrap"><table className="cmp-exact-table"><thead><tr><th>Metric</th><th>Model A</th><th>Model B</th></tr></thead><tbody>
                <tr><td>P50 latency</td><td>{milliseconds(a.latency_p50_ms)}</td><td>{milliseconds(b.latency_p50_ms)}</td></tr>
                <tr><td>P95 latency</td><td>{milliseconds(a.latency_p95_ms)}</td><td>{milliseconds(b.latency_p95_ms)}</td></tr>
                <tr><td>Failure rate</td><td>{percent(a.failure_rate)}</td><td>{percent(b.failure_rate)}</td></tr>
                <tr><td>Observed cases</td><td>{a.observed_case_count}</td><td>{b.observed_case_count}</td></tr>
                <tr><td>Runtime</td><td>{a.runtime_key || '—'}</td><td>{b.runtime_key || '—'}</td></tr>
                <tr><td>CPU</td><td>{a.execution_environment?.cpu_model || 'Not recorded'}</td><td>{b.execution_environment?.cpu_model || 'Not recorded'}</td></tr>
                <tr><td>System / architecture</td><td>{(a.execution_environment?.system || '—') + ' / ' + (a.execution_environment?.machine || '—')}</td><td>{(b.execution_environment?.system || '—') + ' / ' + (b.execution_environment?.machine || '—')}</td></tr>
                <tr><td>Peak process RSS</td><td>{bytes(a.resource_summary.process_rss_bytes_peak)}</td><td>{bytes(b.resource_summary.process_rss_bytes_peak)}</td></tr>
              </tbody></table></div>
            </details>
            <details className="cmp-disclosure"><summary><span>Architecture and generation configuration <small>Parameters, quantization, runtime, seed and temperature</small></span><ChevronDown size={18}/></summary><div className="cmp-parameters"><ModelParametersComparison modelA={a} modelB={b}/></div></details>
          </section>
          <div className="cmp-footer-link"><span>Need a reproducible answer? Check the exact run settings and methodology.</span><ArrowRight size={16}/></div>
        </>;
      })() : <section className="cmp-section cmp-no-data">At least two tested models are needed for comparison.</section>}
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label}/>
    </div>
  );
}
