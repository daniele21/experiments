import { ChevronRight, Info, Sparkles } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import { AppLink } from './Shell';
import type {
  DecisionDatasetSummary,
  DecisionModelSummary,
} from '../types';
import { milliseconds, score, usd } from '../utils';

export function DeploymentBadge({ deployment }: { deployment: string }) {
  const normalized = deployment.toLowerCase();
  return (
    <span className={'deployment-badge ' + normalized}>
      {normalized === 'local' ? 'Local' : normalized === 'api' ? 'API' : deployment}
    </span>
  );
}

export function MetricCard({
  icon,
  label,
  model,
  value,
  caption,
  tone = 'blue',
  onClick,
}: {
  icon: ReactNode;
  label: string;
  model: string;
  value: string;
  caption: string;
  tone?: 'blue' | 'green' | 'amber' | 'violet';
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={'metric-card tone-' + tone}
      onClick={onClick}
    >
      <div className="metric-card-top">
        <span className="metric-icon">{icon}</span>
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-model">{model}</strong>
      <div className="metric-value">{value}</div>
      <span className="metric-caption">{caption}</span>
      <span className="metric-spark" aria-hidden="true">
        <i /><i /><i /><i /><i /><i />
      </span>
    </button>
  );
}

function scaleLog(value: number, min: number, max: number): number {
  if (value <= 0) return 0;
  const lo = Math.log10(Math.max(min, Number.MIN_VALUE));
  const hi = Math.log10(Math.max(max, min * 1.001));
  const point = Math.log10(value);
  return (point - lo) / (hi - lo || 1);
}

export function TradeoffScatter({
  title,
  description,
  models,
  xMetric,
  selectedModel,
  onSelect,
}: {
  title: string;
  description: string;
  models: DecisionModelSummary[];
  xMetric: 'latency' | 'cost';
  selectedModel?: string | null;
  onSelect?: (modelSignature: string) => void;
}) {
  const eligible = models.filter((model) => {
    const x =
      xMetric === 'latency'
        ? model.latency_p50_ms
        : model.provider_cost_per_1k_cases_usd;
    return x != null && x > 0 && model.overall_quality_score != null;
  });
  const xs = eligible.map((model) =>
    xMetric === 'latency'
      ? Number(model.latency_p50_ms)
      : Number(model.provider_cost_per_1k_cases_usd),
  );
  const minX = xs.length ? Math.min(...xs) / 1.7 : 0.01;
  const maxX = xs.length ? Math.max(...xs) * 1.7 : 1000;
  const plotted = eligible.map((model) => {
    const xValue =
      xMetric === 'latency'
        ? Number(model.latency_p50_ms)
        : Number(model.provider_cost_per_1k_cases_usd);
    const x =
      48 +
      Math.max(0, Math.min(1, scaleLog(xValue, minX, maxX))) * 354;
    const quality = Number(model.overall_quality_score);
    const y =
      210 - Math.max(0, Math.min(1, (quality - 40) / 60)) * 170;
    const frontier =
      xMetric === 'latency'
        ? model.observed_quality_latency_pareto
        : model.known_provider_cost_quality_pareto;
    return { model, xValue, x, quality, y, frontier };
  });
  const frontierPoints = plotted
    .filter((point) => point.frontier)
    .sort((a, b) => a.x - b.x);

  return (
    <section className="analysis-card scatter-card">
      <div className="section-heading compact">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span className="info-dot" title="Dashed frontier marks non-dominated observed points.">
          <Info size={14} />
        </span>
      </div>
      {eligible.length ? (
        <div className="scatter-wrap">
          <svg
            className="scatter-svg"
            viewBox="0 0 420 250"
            role="img"
            aria-label={title}
          >
            <g className="scatter-grid">
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <line key={'h' + t} x1="48" x2="402" y1={210 - t * 170} y2={210 - t * 170} />
              ))}
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <line key={'v' + t} y1="40" y2="210" x1={48 + t * 354} x2={48 + t * 354} />
              ))}
            </g>
            {frontierPoints.length > 1 ? (
              <>
                <polyline
                  className="pareto-line"
                  points={frontierPoints
                    .map((point) => point.x + ',' + point.y)
                    .join(' ')}
                />
                <text
                  className="pareto-label"
                  x={frontierPoints[0].x + 8}
                  y={Math.max(32, frontierPoints[0].y - 10)}
                >
                  Pareto frontier
                </text>
              </>
            ) : null}
            {plotted.map(({ model, xValue, x, quality, y, frontier }) => {
              const selected = selectedModel === model.model_signature;
              return (
                <g
                  key={model.model_signature}
                  className={
                    'scatter-point ' +
                    (model.deployment === 'local' ? 'local ' : 'api ') +
                    (selected ? 'selected ' : '') +
                    (frontier ? 'frontier' : '')
                  }
                  onClick={() => onSelect?.(model.model_signature)}
                >
                  <circle cx={x} cy={y} r={selected ? 7 : 5.5}>
                    <title>
                      {model.model_key + ' · quality ' + quality.toFixed(1) +
                        (xMetric === 'latency'
                          ? ' · P50 ' + milliseconds(xValue)
                          : ' · ' + usd(xValue) + ' / 1k cases')}
                    </title>
                  </circle>
                  <text x={Math.min(x + 9, 335)} y={y + 4}>{model.model_key}</text>
                </g>
              );
            })}
            <text className="axis-label" x="8" y="30">100</text>
            <text className="axis-label" x="14" y="214">40</text>
            <text className="axis-title" x="190" y="242">
              {xMetric === 'latency' ? 'Observed latency · P50' : 'Known provider cost / 1k cases'}
            </text>
          </svg>
        </div>
      ) : (
        <div className="empty-visual">No comparable observed points yet.</div>
      )}
    </section>
  );
}

export function QualityLeaderboard({
  models,
  selectedModel,
  onSelect,
}: {
  models: DecisionModelSummary[];
  selectedModel?: string | null;
  onSelect?: (modelSignature: string) => void;
}) {
  const ranked = [...models].sort((a, b) => {
    if (a.quality_coverage_complete !== b.quality_coverage_complete) {
      return a.quality_coverage_complete ? -1 : 1;
    }
    return (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1);
  });
  const max = Math.max(
    ...ranked.map((item) => item.overall_quality_score ?? 0),
    100,
  );
  return (
    <section className="analysis-card leaderboard-card">
      <div className="section-heading compact">
        <div>
          <h2>Overall quality</h2>
          <p>Equal-weight score across the selected comparable capability cohort.</p>
        </div>
        <span className="semantic-chip">policy v1</span>
      </div>
      <div className="leaderboard">
        {ranked.map((model, index) => (
          <button
            type="button"
            key={model.model_signature}
            className={
              selectedModel === model.model_signature
                ? 'leader-row selected'
                : 'leader-row'
            }
            onClick={() => onSelect?.(model.model_signature)}
          >
            <span className="rank">{index + 1}</span>
            <span className="leader-name">
              <strong>{model.model_key}</strong>
              <span>
                <DeploymentBadge deployment={model.deployment} />
                {!model.quality_coverage_complete ? (
                  <em>Partial coverage</em>
                ) : null}
              </span>
            </span>
            <span className="leader-bar">
              <i
                style={{
                  width:
                    ((model.overall_quality_score ?? 0) / max) * 100 + '%',
                }}
              />
            </span>
            <strong className="leader-score">{score(model.overall_quality_score)}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}

export function DatasetHeatmap({
  datasets,
  models,
  view = 'score',
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
  view?: 'score' | 'delta' | 'rank';
}) {
  const modelKeys = models.map((model) => model.model_key);
  const rows = Array.from(
    new Map(
      datasets.map((row) => [
        row.capability_id + '::' + row.dataset_id,
        {
          capability_id: row.capability_id,
          dataset_id: row.dataset_id,
          sample_count: row.sample_count,
        },
      ]),
    ).values(),
  ).sort((a, b) =>
    (a.capability_id + a.dataset_id).localeCompare(
      b.capability_id + b.dataset_id,
    ),
  );

  const byCell = new Map(
    datasets.map((row) => [
      row.model_key + '::' + row.capability_id + '::' + row.dataset_id,
      row,
    ]),
  );

  return (
    <section className="analysis-card heatmap-card">
      <div className="section-heading compact">
        <div>
          <h2>Performance by dataset</h2>
          <p>Drill from capability into the datasets that explain the aggregate score.</p>
        </div>
        <span className="semantic-chip">{view === 'score' ? 'Score' : view}</span>
      </div>
      <div className="heatmap-scroll">
        <div
          className="heatmap-grid"
          style={{ '--model-count': modelKeys.length } as CSSProperties}
        >
          <div className="heatmap-head">Capability / dataset</div>
          <div className="heatmap-head samples">n</div>
          {models.map((model) => (
            <div className="heatmap-head model" key={model.model_signature}>
              <span>{model.model_key}</span>
              <DeploymentBadge deployment={model.deployment} />
            </div>
          ))}
          {rows.map((row) => {
            const available = modelKeys
              .map((modelKey) =>
                byCell.get(modelKey + '::' + row.capability_id + '::' + row.dataset_id),
              )
              .filter((value): value is DecisionDatasetSummary => Boolean(value));
            const scores = available
              .map((item) => item.normalized_quality_score)
              .filter((value): value is number => value != null);
            const best = scores.length ? Math.max(...scores) : null;
            const ranks = [...available]
              .sort(
                (a, b) =>
                  (b.normalized_quality_score ?? -1) -
                  (a.normalized_quality_score ?? -1),
              )
              .map((item, index) => [item.model_key, index + 1] as const);
            const rankMap = new Map(ranks);
            return (
              <div className="heatmap-row contents" key={row.capability_id + row.dataset_id}>
                <AppLink
                  href={'/datasets/' + encodeURIComponent(row.dataset_id)}
                  className="heatmap-label"
                >
                  <span>{row.capability_id.replaceAll('-', ' ')}</span>
                  <strong>{row.dataset_id}</strong>
                  <ChevronRight size={14} />
                </AppLink>
                <div className="heatmap-samples">{row.sample_count}</div>
                {modelKeys.map((modelKey) => {
                  const cell = byCell.get(
                    modelKey + '::' + row.capability_id + '::' + row.dataset_id,
                  );
                  const value = cell?.normalized_quality_score ?? null;
                  const delta =
                    value != null && best != null ? value - best : null;
                  const display =
                    view === 'rank'
                      ? cell
                        ? '#' + rankMap.get(modelKey)
                        : '—'
                      : view === 'delta'
                        ? delta == null
                          ? '—'
                          : delta === 0
                            ? 'best'
                            : delta.toFixed(1)
                        : score(value);
                  const heat = value == null ? 0 : Math.max(0, Math.min(1, value / 100));
                  return (
                    <div
                      key={modelKey}
                      className="heatmap-cell"
                      style={{ '--heat': heat } as CSSProperties}
                      title={
                        cell
                          ? [
                              modelKey,
                              'score ' + score(value),
                              'P50 ' + milliseconds(cell.latency_p50_ms),
                              cell.provider_cost_known
                                ? usd(cell.provider_cost_per_1k_cases_usd) + ' / 1k cases'
                                : 'provider cost N/A',
                            ].join(' · ')
                          : 'No CURRENT comparable result'
                      }
                    >
                      {display}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function MethodologyAccordion({
  policyLabel,
}: {
  policyLabel?: string;
}) {
  return (
    <div className="methodology-row" id="methodology">
      <details>
        <summary>
          <span><Sparkles size={17} /> Methodology</span>
          <small>Datasets, scoring and normalization</small>
        </summary>
        <p>
          Task-specific primary metrics remain authoritative. The overall quality
          index is a versioned navigation aid and never replaces capability-level
          evidence.
        </p>
      </details>
      <details>
        <summary>
          <span><Info size={17} /> CURRENT policy</span>
          <small>Latest valid comparable evidence</small>
        </summary>
        <p>
          Partial or failed runs remain visible in Runs, but never replace the
          latest valid completed comparable result.
        </p>
      </details>
      <details>
        <summary>
          <span><Info size={17} /> Quality policy</span>
          <small>{policyLabel ?? 'Explicit versioned aggregation'}</small>
        </summary>
        <p>
          Coverage is explicit. Models missing required capabilities are marked
          partial rather than silently receiving a zero.
        </p>
      </details>
    </div>
  );
}
