import {
  BadgeDollarSign,
  Layers3,
  ShieldCheck,
  Sparkles,
  Trophy,
  Zap,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { overview } from '../data';
import type {
  DecisionCapabilitySummary,
  DecisionModelSummary,
} from '../types';
import { AppLink } from '../components/Shell';

export type ExecutiveView =
  | 'quality'
  | 'speed'
  | 'cost'
  | 'capabilities'
  | 'reliability';

const EXECUTIVE_VIEWS: Array<{
  id: ExecutiveView;
  label: string;
  href: string;
}> = [
  { id: 'quality', label: 'Quality', href: '/executive/quality' },
  { id: 'speed', label: 'Speed', href: '/executive/speed' },
  { id: 'cost', label: 'Cost', href: '/executive/cost' },
  { id: 'capabilities', label: 'Capabilities', href: '/executive/capabilities' },
  { id: 'reliability', label: 'Reliability', href: '/executive/reliability' },
];

function scoreValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toFixed(1);
}

function latencyValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)} s`;
}

function costValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(2)}`;
}

function failureValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const percent = value <= 1 ? value * 100 : value;
  return `${percent.toFixed(percent < 10 ? 1 : 0)}%`;
}

function modelQuality(model: DecisionModelSummary): number {
  return model.overall_quality_score ?? -1;
}

function ExecutiveFrame({
  active,
  eyebrow,
  title,
  statement,
  evidence,
  children,
}: {
  active: ExecutiveView;
  eyebrow: string;
  title: string;
  statement: string;
  evidence?: string;
  children: ReactNode;
}) {
  return (
    <div className="executive-page">
      <header className="executive-header">
        <div className="executive-title-lockup">
          <div className="executive-mark"><Sparkles size={17} /></div>
          <div>
            <span className="executive-eyebrow">{eyebrow}</span>
            <h1>{title}</h1>
          </div>
        </div>
        <nav className="executive-tabs" aria-label="Executive insight views">
          {EXECUTIVE_VIEWS.map((view) => (
            <AppLink
              key={view.id}
              href={view.href}
              className={active === view.id ? 'executive-tab active' : 'executive-tab'}
            >
              {view.label}
            </AppLink>
          ))}
        </nav>
      </header>

      <section className="executive-story">
        <div className="executive-story-copy">
          <span>Decision signal</span>
          <h2>{statement}</h2>
          {evidence ? <p>{evidence}</p> : null}
        </div>
      </section>

      {children}
    </div>
  );
}

function ExecutiveEmpty({ message }: { message: string }) {
  return (
    <div className="executive-empty">
      <Sparkles size={22} />
      <strong>Evidence not available yet</strong>
      <span>{message}</span>
    </div>
  );
}

function QualityBars({ models }: { models: DecisionModelSummary[] }) {
  const ranked = [...models]
    .filter((model) => model.overall_quality_score != null)
    .sort((a, b) => modelQuality(b) - modelQuality(a));
  if (!ranked.length) {
    return <ExecutiveEmpty message="Project completed benchmark results to compare overall quality." />;
  }
  const max = Math.max(...ranked.map((model) => modelQuality(model)), 1);
  return (
    <div className="executive-ranking">
      {ranked.map((model, index) => {
        const value = modelQuality(model);
        return (
          <div className={index === 0 ? 'executive-rank-row winner' : 'executive-rank-row'} key={model.model_signature}>
            <span className="executive-rank-number">{index + 1}</span>
            <div className="executive-rank-model">
              <strong>{model.model_key}</strong>
              <span>{model.deployment === 'local' ? 'Local' : 'API'}{model.family ? ` · ${model.family}` : ''}</span>
            </div>
            <div className="executive-rank-track">
              <i style={{ width: `${Math.max(2, (value / max) * 100)}%` }} />
            </div>
            <strong className="executive-rank-value">{scoreValue(value)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function TradeoffPlot({
  models,
  x,
  xLabel,
  formatX,
  pareto,
}: {
  models: DecisionModelSummary[];
  x: (model: DecisionModelSummary) => number | null;
  xLabel: string;
  formatX: (value: number | null | undefined) => string;
  pareto: (model: DecisionModelSummary) => boolean;
}) {
  const points = models
    .map((model) => ({ model, xv: x(model), yv: model.overall_quality_score }))
    .filter(
      (item): item is { model: DecisionModelSummary; xv: number; yv: number } =>
        item.xv != null &&
        Number.isFinite(item.xv) &&
        item.yv != null &&
        Number.isFinite(item.yv),
    );
  if (!points.length) {
    return <ExecutiveEmpty message={`No comparable ${xLabel.toLowerCase()} evidence is available for the current projected results.`} />;
  }

  const xs = points.map((point) => point.xv);
  const ys = points.map((point) => point.yv);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xScale = (value: number) =>
    maxX === minX ? 450 : 90 + ((value - minX) / (maxX - minX)) * 720;
  const yScale = (value: number) =>
    maxY === minY ? 160 : 276 - ((value - minY) / (maxY - minY)) * 220;

  return (
    <div className="executive-plot-shell">
      <svg className="executive-plot" viewBox="0 0 900 340" role="img" aria-label={`Quality versus ${xLabel}`}>
        <g className="executive-plot-grid">
          {[0, 1, 2, 3, 4].map((step) => {
            const yy = 56 + step * 55;
            return <line key={step} x1="76" y1={yy} x2="840" y2={yy} />;
          })}
        </g>
        <line x1="76" y1="286" x2="840" y2="286" className="executive-axis" />
        <line x1="76" y1="44" x2="76" y2="286" className="executive-axis" />
        {points.map(({ model, xv, yv }) => {
          const cx = xScale(xv);
          const cy = yScale(yv);
          const onPareto = pareto(model);
          const toLeft = cx > 690;
          return (
            <g className={onPareto ? 'executive-point pareto' : 'executive-point'} key={model.model_signature}>
              <circle cx={cx} cy={cy} r={onPareto ? 8 : 6} />
              <text x={toLeft ? cx - 11 : cx + 11} y={cy - 5} textAnchor={toLeft ? 'end' : 'start'}>
                {model.model_key}
              </text>
              <text className="meta" x={toLeft ? cx - 11 : cx + 11} y={cy + 9} textAnchor={toLeft ? 'end' : 'start'}>
                {formatX(xv)}
              </text>
            </g>
          );
        })}
        <text x="460" y="328" textAnchor="middle" className="executive-axis-title">{xLabel} · lower is better</text>
        <text x="20" y="165" textAnchor="middle" transform="rotate(-90 20 165)" className="executive-axis-title">
          Quality · higher is better
        </text>
      </svg>
    </div>
  );
}

function CapabilityLeadership({
  capabilities,
}: {
  capabilities: DecisionCapabilitySummary[];
}) {
  const byCapability = new Map<string, DecisionCapabilitySummary[]>();
  for (const row of capabilities) {
    const values = byCapability.get(row.capability_id) ?? [];
    values.push(row);
    byCapability.set(row.capability_id, values);
  }
  const winners = [...byCapability.entries()]
    .map(([capability, rows]) => {
      const ranked = [...rows]
        .filter((row) => row.normalized_quality_score != null)
        .sort((a, b) => Number(b.normalized_quality_score) - Number(a.normalized_quality_score));
      return {
        capability,
        winner: ranked[0],
        runnerUp: ranked[1],
      };
    })
    .filter((item) => item.winner);

  if (!winners.length) {
    return <ExecutiveEmpty message="Complete and project capability runs to surface capability leaders." />;
  }

  return (
    <div className="executive-capability-list">
      {winners.map(({ capability, winner, runnerUp }) => {
        const value = Number(winner?.normalized_quality_score ?? 0);
        const runner = Number(runnerUp?.normalized_quality_score ?? 0);
        const gap = runnerUp ? value - runner : null;
        return (
          <div className="executive-capability-row" key={capability}>
            <div>
              <span>{capability.replaceAll('-', ' ')}</span>
              <strong>{winner?.model_key}</strong>
            </div>
            <div className="executive-capability-track">
              <i style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
            </div>
            <div className="executive-capability-score">
              <strong>{scoreValue(value)}</strong>
              <span>{gap == null ? 'leader' : `+${gap.toFixed(1)} vs #2`}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ReliabilityBars({ models }: { models: DecisionModelSummary[] }) {
  const rows = [...models]
    .filter((model) => model.failure_rate != null)
    .sort((a, b) => Number(a.failure_rate) - Number(b.failure_rate));
  if (!rows.length) {
    return <ExecutiveEmpty message="Failure-rate evidence is not available in the projected CURRENT cohort." />;
  }
  const max = Math.max(...rows.map((model) => Number(model.failure_rate)), 0.01);
  return (
    <div className="executive-reliability">
      {rows.map((model, index) => {
        const raw = Number(model.failure_rate);
        const width = Math.max(1.5, (raw / max) * 100);
        return (
          <div className={index === 0 ? 'executive-reliability-row best' : 'executive-reliability-row'} key={model.model_signature}>
            <div>
              <strong>{model.model_key}</strong>
              <span>
                {model.quality_coverage_complete ? 'Complete quality coverage' : 'Partial quality coverage'}
              </span>
            </div>
            <div className="executive-reliability-track">
              <i style={{ width: `${width}%` }} />
            </div>
            <strong>{failureValue(raw)}</strong>
          </div>
        );
      })}
    </div>
  );
}

export function ExecutivePage({ view }: { view: ExecutiveView }) {
  const decision = overview.decision;
  const models = decision?.model_summaries ?? [];
  const capabilities = decision?.capability_summaries ?? [];

  const qualityModels = [...models]
    .filter((model) => model.overall_quality_score != null)
    .sort((a, b) => modelQuality(b) - modelQuality(a));
  const qualityLeader =
    qualityModels.find((model) => model.quality_coverage_complete) ?? qualityModels[0];

  const speedModels = models.filter((model) => model.latency_p50_ms != null && model.overall_quality_score != null);
  const speedPareto = speedModels.filter((model) => model.observed_quality_latency_pareto);
  const speedChoice =
    [...speedPareto].sort((a, b) => modelQuality(b) - modelQuality(a))[0] ??
    [...speedModels].sort((a, b) => Number(a.latency_p50_ms) - Number(b.latency_p50_ms))[0];

  const costModels = models.filter(
    (model) =>
      model.deployment !== 'local' &&
      model.provider_cost_known &&
      model.provider_cost_per_1k_cases_usd != null &&
      model.overall_quality_score != null,
  );
  const costPareto = costModels.filter((model) => model.known_provider_cost_quality_pareto);
  const costChoice =
    [...costPareto].sort((a, b) => modelQuality(b) - modelQuality(a))[0] ??
    [...costModels].sort(
      (a, b) => Number(a.provider_cost_per_1k_cases_usd) - Number(b.provider_cost_per_1k_cases_usd),
    )[0];

  const reliableModels = [...models]
    .filter((model) => model.failure_rate != null)
    .sort((a, b) => Number(a.failure_rate) - Number(b.failure_rate));
  const reliabilityLeader = reliableModels[0];

  if (view === 'quality') {
    const runnerUp = qualityModels[1];
    const margin =
      qualityLeader && runnerUp
        ? modelQuality(qualityLeader) - modelQuality(runnerUp)
        : null;
    return (
      <ExecutiveFrame
        active="quality"
        eyebrow="Executive · Quality"
        title="Who is strongest overall?"
        statement={
          qualityLeader
            ? `${qualityLeader.model_key} leads the CURRENT cohort on overall benchmark quality.`
            : 'No quality leader can be established yet.'
        }
        evidence={
          qualityLeader
            ? `Score ${scoreValue(qualityLeader.overall_quality_score)}${margin == null ? '' : ` · ${margin.toFixed(1)} points ahead of #2`}.`
            : 'Project completed comparable results to establish a quality leader.'
        }
      >
        <section className="executive-visual-card">
          <div className="executive-visual-heading">
            <div>
              <span>Overall quality ranking</span>
              <h3>Higher is better</h3>
            </div>
            <Trophy size={20} />
          </div>
          <QualityBars models={models} />
        </section>
      </ExecutiveFrame>
    );
  }

  if (view === 'speed') {
    return (
      <ExecutiveFrame
        active="speed"
        eyebrow="Executive · Speed"
        title="Where is the quality–speed sweet spot?"
        statement={
          speedChoice
            ? `${speedChoice.model_key} is the strongest measured quality–latency trade-off in the current evidence.`
            : 'There is not enough latency evidence to identify a speed trade-off.'
        }
        evidence={
          speedChoice
            ? `${scoreValue(speedChoice.overall_quality_score)} quality at ${latencyValue(speedChoice.latency_p50_ms)} P50.`
            : 'Run comparable performance evidence on the same execution lineage.'
        }
      >
        <section className="executive-visual-card">
          <div className="executive-visual-heading">
            <div>
              <span>Quality × observed latency</span>
              <h3>Upper-left is the executive target</h3>
            </div>
            <Zap size={20} />
          </div>
          <TradeoffPlot
            models={speedModels}
            x={(model) => model.latency_p50_ms}
            xLabel="P50 latency"
            formatX={latencyValue}
            pareto={(model) => model.observed_quality_latency_pareto}
          />
        </section>
      </ExecutiveFrame>
    );
  }

  if (view === 'cost') {
    return (
      <ExecutiveFrame
        active="cost"
        eyebrow="Executive · Cost"
        title="How much are we paying for quality?"
        statement={
          costChoice
            ? `${costChoice.model_key} offers the strongest measured quality–cost position among priced API models.`
            : 'There is not enough priced API evidence to establish a cost winner.'
        }
        evidence={
          costChoice
            ? `${scoreValue(costChoice.overall_quality_score)} quality at ${costValue(costChoice.provider_cost_per_1k_cases_usd)} per 1k benchmark cases.`
            : 'Known provider pricing is required; local runtime cost is never treated as zero.'
        }
      >
        <section className="executive-visual-card">
          <div className="executive-visual-heading">
            <div>
              <span>Quality × known provider cost</span>
              <h3>Buy the most quality for the least spend</h3>
            </div>
            <BadgeDollarSign size={20} />
          </div>
          <TradeoffPlot
            models={costModels}
            x={(model) => model.provider_cost_per_1k_cases_usd}
            xLabel="Cost / 1k cases"
            formatX={costValue}
            pareto={(model) => model.known_provider_cost_quality_pareto}
          />
        </section>
      </ExecutiveFrame>
    );
  }

  if (view === 'capabilities') {
    const counts = new Map<string, number>();
    const byCapability = new Map<string, DecisionCapabilitySummary[]>();
    for (const row of capabilities) {
      byCapability.set(row.capability_id, [...(byCapability.get(row.capability_id) ?? []), row]);
    }
    for (const rows of byCapability.values()) {
      const winner = [...rows]
        .filter((row) => row.normalized_quality_score != null)
        .sort((a, b) => Number(b.normalized_quality_score) - Number(a.normalized_quality_score))[0];
      if (winner) counts.set(winner.model_key, (counts.get(winner.model_key) ?? 0) + 1);
    }
    const mostWins = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    return (
      <ExecutiveFrame
        active="capabilities"
        eyebrow="Executive · Capability leadership"
        title="Where does each model actually win?"
        statement={
          mostWins
            ? `${mostWins[0]} leads the most measured capability verticals.`
            : 'Capability leadership is not available yet.'
        }
        evidence={
          mostWins
            ? `${mostWins[1]} capability win${mostWins[1] === 1 ? '' : 's'} in the projected CURRENT cohort.`
            : 'Complete capability evidence to identify winners by task vertical.'
        }
      >
        <section className="executive-visual-card">
          <div className="executive-visual-heading">
            <div>
              <span>Capability winners</span>
              <h3>One winner per task vertical</h3>
            </div>
            <Layers3 size={20} />
          </div>
          <CapabilityLeadership capabilities={capabilities} />
        </section>
      </ExecutiveFrame>
    );
  }

  return (
    <ExecutiveFrame
      active="reliability"
      eyebrow="Executive · Reliability"
      title="Which model can we trust operationally?"
      statement={
        reliabilityLeader
          ? `${reliabilityLeader.model_key} has the lowest observed failure rate in the CURRENT cohort.`
          : 'Reliability cannot be ranked with the current evidence.'
      }
      evidence={
        reliabilityLeader
          ? `${failureValue(reliabilityLeader.failure_rate)} observed failures · ${reliabilityLeader.quality_coverage_complete ? 'complete' : 'partial'} quality coverage.`
          : 'Failure-rate evidence is required before making an operational reliability claim.'
      }
    >
      <section className="executive-visual-card">
        <div className="executive-visual-heading">
          <div>
            <span>Observed model failure rate</span>
            <h3>Lower is better</h3>
          </div>
          <ShieldCheck size={20} />
        </div>
        <ReliabilityBars models={models} />
      </section>
    </ExecutiveFrame>
  );
}
