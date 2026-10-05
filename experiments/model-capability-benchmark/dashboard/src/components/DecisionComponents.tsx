import { ChevronRight, Info, Maximize2, Sparkles, Trophy, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { AppLink } from './Shell';
import type {
  DecisionDatasetSummary,
  DecisionModelSummary,
} from '../types';
import { milliseconds, providerCostCoverage, score, usd } from '../utils';
import { modelShortLabel, modelVisual } from '../modelVisuals';
import { ModelLegend, ModelMarker } from './ModelExplorerControls';

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
  hoveredModel,
  onSelect,
  onHover,
}: {
  title: string;
  description: string;
  models: DecisionModelSummary[];
  xMetric: 'latency' | 'cost';
  selectedModel?: string | null;
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onHover?: (modelSignature: string | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);
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
  const minX = xs.length ? Math.min(...xs) / 1.35 : 0.01;
  const maxX = xs.length ? Math.max(...xs) * 1.35 : 1000;
  const plotted = eligible.map((model) => {
    const xValue =
      xMetric === 'latency'
        ? Number(model.latency_p50_ms)
        : Number(model.provider_cost_per_1k_cases_usd);
    const x =
      72 +
      Math.max(0, Math.min(1, scaleLog(xValue, minX, maxX))) * 468;
    const quality = Number(model.overall_quality_score);
    const y = 272 - Math.max(0, Math.min(1, quality / 100)) * 220;
    const frontier =
      xMetric === 'latency'
        ? model.observed_quality_latency_pareto
        : model.known_provider_cost_quality_pareto;
    return { model, xValue, x, quality, y, frontier };
  });
  const frontierPoints = plotted
    .filter((point) => point.frontier)
    .sort((a, b) => a.x - b.x);

  const complete = models.filter((m) => m.provider_cost_status === 'complete').length;
  const partial = models.filter((m) => m.provider_cost_status === 'partial').length;
  const local = models.filter((m) => m.provider_cost_status === 'local_not_applicable').length;
  const unavailable = models.filter((m) => m.provider_cost_status === 'unavailable').length;

  const chart = (
    <div className={expanded ? 'scatter-wrap expanded' : 'scatter-wrap'}>
      {xMetric === 'cost' ? (
        <div className="scatter-coverage-summary">
          <span><b>{eligible.length}</b> plotted</span>
          <span><b>{complete}</b> complete</span>
          <span><b>{partial}</b> partial</span>
          <span><b>{local}</b> local N/A</span>
          <span><b>{unavailable}</b> unavailable</span>
        </div>
      ) : null}
      {eligible.length ? (
        <svg
          className="scatter-svg"
          viewBox="0 0 600 330"
          role="img"
          aria-label={title}
        >
          <g className="scatter-grid">
            {[0, 25, 50, 75, 100].map((tick) => {
              const y = 272 - (tick / 100) * 220;
              return (
                <g key={'y' + tick}>
                  <line x1="72" x2="540" y1={y} y2={y} />
                  <text className="axis-label" x="42" y={y + 3}>{tick}</text>
                </g>
              );
            })}
            {[0, 0.25, 0.5, 0.75, 1].map((t) => (
              <line key={'v' + t} y1="52" y2="272" x1={72 + t * 468} x2={72 + t * 468} />
            ))}
          </g>
          {frontierPoints.length > 1 ? (
            <polyline
              className="pareto-line"
              points={frontierPoints.map((point) => point.x + ',' + point.y).join(' ')}
            />
          ) : null}
          {plotted.map(({ model, xValue, x, quality, y, frontier }, index) => {
            const visual = modelVisual(model.model_signature);
            const selected = selectedModel === model.model_signature;
            const hovered = hoveredModel === model.model_signature;
            const dimmed = Boolean(hoveredModel && !hovered);
            const showLabel = expanded || selected || hovered || frontier || plotted.length <= 6;
            const labelRight = x < 410;
            const labelY = y + (index % 2 === 0 ? -10 : 15);
            return (
              <g
                key={model.model_signature}
                className={
                  'scatter-point ' +
                  (selected ? 'selected ' : '') +
                  (hovered ? 'hovered ' : '') +
                  (dimmed ? 'dimmed ' : '') +
                  (frontier ? 'frontier ' : '') +
                  (xMetric === 'cost' && model.provider_cost_status === 'partial'
                    ? 'cost-partial'
                    : '')
                }
                onClick={() => onSelect?.(model.model_signature)}
                onMouseEnter={() => onHover?.(model.model_signature)}
                onMouseLeave={() => onHover?.(null)}
              >
                <circle
                  cx={x}
                  cy={y}
                  r={selected || hovered ? 8 : 6}
                  style={{ fill: visual.color }}
                >
                  <title>
                    {model.model_key + ' · quality ' + quality.toFixed(1) +
                      (xMetric === 'latency'
                        ? ' · P50 ' + milliseconds(xValue)
                        : ' · ' + usd(xValue) + ' / 1k · ' +
                          providerCostCoverage(
                            model.provider_cost_status,
                            model.provider_cost_priced_cases,
                            model.provider_cost_total_cases,
                            model.provider_cost_coverage_rate,
                          ))}
                  </title>
                </circle>
                {showLabel ? (
                  <text
                    x={labelRight ? x + 10 : x - 10}
                    y={labelY}
                    textAnchor={labelRight ? 'start' : 'end'}
                  >
                    {modelShortLabel(model.model_key)}
                  </text>
                ) : null}
              </g>
            );
          })}
          <text className="axis-title axis-y-title" x="10" y="160" transform="rotate(-90 10 160)">
            Quality score
          </text>
          <text className="axis-title" x="236" y="318">
            {xMetric === 'latency'
              ? 'Observed latency · P50'
              : 'Known provider cost / 1k cases'}
          </text>
        </svg>
      ) : (
        <div className="empty-visual scatter-empty">
          <strong>No priced models in the current selection.</strong>
          <span>
            {xMetric === 'cost'
              ? 'Select API models with complete or partial frozen pricing, or reset the model filters.'
              : 'No selected models have observed latency evidence.'}
          </span>
        </div>
      )}
    </div>
  );

  return (
    <>
      <section className="analysis-card scatter-card">
        <div className="section-heading compact">
          <div>
            <h2>{title}</h2>
            <p>{description}</p>
          </div>
          <div className="chart-card-actions">
            <button
              type="button"
              className="info-dot"
              title="Dashed frontier marks non-dominated comparable points."
            >
              <Info size={14} />
            </button>
            <button
              type="button"
              className="expand-chart-button"
              onClick={() => setExpanded(true)}
              title={'Expand ' + title}
            >
              <Maximize2 size={15} />
            </button>
          </div>
        </div>
        {chart}
        <ModelLegend
          models={eligible}
          hoveredModel={hoveredModel}
          selectedModel={selectedModel}
          onHover={onHover}
          onSelect={onSelect}
          compact
        />
      </section>

      {expanded ? (
        <div className="chart-modal-backdrop" role="presentation" onMouseDown={() => setExpanded(false)}>
          <section
            className="chart-modal"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="chart-modal-header">
              <div>
                <span className="eyebrow">Analytical workspace</span>
                <h2>{title}</h2>
                <p>{description}</p>
              </div>
              <button type="button" className="modal-close" onClick={() => setExpanded(false)}>
                <X size={18} />
              </button>
            </header>
            <div className="chart-modal-grid">
              <div className="chart-modal-canvas">
                {chart}
                <ModelLegend
                  models={eligible}
                  hoveredModel={hoveredModel}
                  selectedModel={selectedModel}
                  onHover={onHover}
                  onSelect={onSelect}
                />
              </div>
              <aside className="chart-modal-insights">
                <h3>What to read</h3>
                <dl>
                  <div><dt>Best quality</dt><dd>{[...eligible].sort((a,b) => Number(b.overall_quality_score) - Number(a.overall_quality_score))[0]?.model_key ?? '—'}</dd></div>
                  <div><dt>{xMetric === 'latency' ? 'Fastest observed' : 'Lowest priced'}</dt><dd>{[...eligible].sort((a,b) => Number(xMetric === 'latency' ? a.latency_p50_ms : a.provider_cost_per_1k_cases_usd) - Number(xMetric === 'latency' ? b.latency_p50_ms : b.provider_cost_per_1k_cases_usd))[0]?.model_key ?? '—'}</dd></div>
                  <div><dt>Pareto models</dt><dd>{frontierPoints.length}</dd></div>
                  <div><dt>Visible models</dt><dd>{models.length}</dd></div>
                </dl>
                {xMetric === 'cost' ? (
                  <div className="modal-note">
                    Local runtime cost is intentionally excluded. Partial pricing is shown, but the cost Pareto frontier uses complete pricing only.
                  </div>
                ) : (
                  <div className="modal-note">
                    Latency is observed execution performance and can reflect different hardware/runtime environments.
                  </div>
                )}
              </aside>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

export function QualityLeaderboard({
  models,
  selectedModel,
  hoveredModel,
  onSelect,
  onHover,
}: {
  models: DecisionModelSummary[];
  selectedModel?: string | null;
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onHover?: (modelSignature: string | null) => void;
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
              'leader-row ' +
              (selectedModel === model.model_signature ? 'selected ' : '') +
              (hoveredModel && hoveredModel !== model.model_signature ? 'dimmed' : '')
            }
            onClick={() => onSelect?.(model.model_signature)}
            onMouseEnter={() => onHover?.(model.model_signature)}
            onMouseLeave={() => onHover?.(null)}
          >
            <span className="rank">{index + 1}</span>
            <span className="leader-name">
              <strong><ModelMarker signature={model.model_signature} /> {model.model_key}</strong>
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
                  background: modelVisual(model.model_signature).color,
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


type DatasetLandscapeView = 'score' | 'delta' | 'rank';
type DatasetLandscapeSort = 'discriminative' | 'hardest' | 'alphabetical';

interface DatasetLandscapeRow {
  capability_id: string;
  dataset_id: string;
  sample_count: number;
  best_score: number | null;
  worst_score: number | null;
  average_score: number | null;
  spread: number | null;
  winner_model_key: string | null;
  best_local_model_key: string | null;
  values: DecisionDatasetSummary[];
}

function buildDatasetLandscapeRows(
  datasets: DecisionDatasetSummary[],
  models: DecisionModelSummary[],
): DatasetLandscapeRow[] {
  const grouped = new Map<string, DecisionDatasetSummary[]>();
  datasets.forEach((row) => {
    const key = row.capability_id + '::' + row.dataset_id;
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  });
  const localKeys = new Set(
    models.filter((model) => model.deployment === 'local').map((model) => model.model_key),
  );
  return [...grouped.entries()].map(([key, values]) => {
    const scored = values.filter((row) => row.normalized_quality_score != null);
    const sorted = [...scored].sort(
      (a, b) => Number(b.normalized_quality_score) - Number(a.normalized_quality_score),
    );
    const local = sorted.find((row) => localKeys.has(row.model_key));
    const scores = scored.map((row) => Number(row.normalized_quality_score));
    const best = scores.length ? Math.max(...scores) : null;
    const worst = scores.length ? Math.min(...scores) : null;
    const [capability_id, dataset_id] = key.split('::');
    return {
      capability_id,
      dataset_id,
      sample_count: values[0]?.sample_count ?? 0,
      best_score: best,
      worst_score: worst,
      average_score: scores.length
        ? scores.reduce((total, value) => total + value, 0) / scores.length
        : null,
      spread: best != null && worst != null ? best - worst : null,
      winner_model_key: sorted[0]?.model_key ?? null,
      best_local_model_key: local?.model_key ?? null,
      values,
    };
  });
}

export function DatasetPerformanceLandscape({
  datasets,
  models,
  selectedModel,
  hoveredModel,
  onSelect,
  onHover,
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
  selectedModel?: string | null;
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onHover?: (modelSignature: string | null) => void;
}) {
  const [view, setView] = useState<DatasetLandscapeView>('score');
  const [sortMode, setSortMode] = useState<DatasetLandscapeSort>('discriminative');
  const rows = useMemo(
    () => buildDatasetLandscapeRows(datasets, models),
    [datasets, models],
  );
  const sortedRows = useMemo(() => {
    const result = [...rows];
    if (sortMode === 'hardest') {
      return result.sort(
        (a, b) => Number(a.average_score ?? 999) - Number(b.average_score ?? 999),
      );
    }
    if (sortMode === 'alphabetical') {
      return result.sort((a, b) => a.dataset_id.localeCompare(b.dataset_id));
    }
    return result.sort((a, b) => Number(b.spread ?? -1) - Number(a.spread ?? -1));
  }, [rows, sortMode]);

  const winCounts = new Map<string, number>();
  rows.forEach((row) => {
    if (row.winner_model_key) {
      winCounts.set(row.winner_model_key, (winCounts.get(row.winner_model_key) ?? 0) + 1);
    }
  });
  const mostWins = [...winCounts.entries()].sort((a, b) => b[1] - a[1])[0];
  const hardest = [...rows]
    .filter((row) => row.average_score != null)
    .sort((a, b) => Number(a.average_score) - Number(b.average_score))[0];
  const discriminative = [...rows]
    .filter((row) => row.spread != null)
    .sort((a, b) => Number(b.spread) - Number(a.spread))[0];
  const localWins = new Map<string, number>();
  rows.forEach((row) => {
    if (row.best_local_model_key) {
      localWins.set(
        row.best_local_model_key,
        (localWins.get(row.best_local_model_key) ?? 0) + 1,
      );
    }
  });
  const bestLocal = [...localWins.entries()].sort((a, b) => b[1] - a[1])[0];

  return (
    <section className="analysis-card dataset-landscape-card">
      <div className="section-heading">
        <div>
          <h2>Dataset performance landscape</h2>
          <p>See who wins where, how large each gap is and which datasets discriminate most.</p>
        </div>
        <div className="dataset-landscape-controls">
          <div className="segmented">
            {(['score', 'delta', 'rank'] as const).map((item) => (
              <button
                key={item}
                type="button"
                className={view === item ? 'active' : ''}
                onClick={() => setView(item)}
              >
                {item === 'score' ? 'Score' : item === 'delta' ? 'Delta vs best' : 'Rank'}
              </button>
            ))}
          </div>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as DatasetLandscapeSort)}
          >
            <option value="discriminative">Most discriminative</option>
            <option value="hardest">Hardest</option>
            <option value="alphabetical">Alphabetical</option>
          </select>
        </div>
      </div>

      <ModelLegend
        models={models}
        hoveredModel={hoveredModel}
        selectedModel={selectedModel}
        onHover={onHover}
        onSelect={onSelect}
        compact={models.length > 8}
      />

      <div className="dataset-insight-chips">
        <div><Trophy size={14}/><span>Most wins</span><strong>{mostWins ? mostWins[0] + ' · ' + mostWins[1] : '—'}</strong></div>
        <div><span>Best local</span><strong>{bestLocal ? bestLocal[0] : '—'}</strong></div>
        <div><span>Hardest</span><strong>{hardest?.dataset_id ?? '—'}</strong></div>
        <div><span>Most discriminative</span><strong>{discriminative?.dataset_id ?? '—'}</strong></div>
      </div>

      <div className="dataset-landscape-list">
        {sortedRows.map((row) => {
          const ranked = [...row.values]
            .filter((item) => item.normalized_quality_score != null)
            .sort(
              (a, b) =>
                Number(b.normalized_quality_score) - Number(a.normalized_quality_score),
            );
          const rankMap = new Map(ranked.map((item, index) => [item.model_key, index + 1]));
          return (
            <AppLink
              key={row.capability_id + row.dataset_id}
              href={'/datasets/' + encodeURIComponent(row.dataset_id)}
              className="dataset-landscape-row"
            >
              <div className="dataset-landscape-meta">
                <span>{row.capability_id.replaceAll('-', ' ')}</span>
                <strong>{row.dataset_id}</strong>
                <small>
                  winner {row.winner_model_key ?? '—'} · spread {row.spread?.toFixed(1) ?? '—'}
                </small>
              </div>
              <div
                className="dataset-landscape-track"
                style={{
                  height: Math.max(44, Math.min(220, models.length * 10 + 20)),
                }}
              >
                {models.map((model, modelIndex) => {
                  const value = row.values.find((item) => item.model_key === model.model_key);
                  const scoreValue = value?.normalized_quality_score ?? null;
                  const delta =
                    scoreValue != null && row.best_score != null
                      ? scoreValue - row.best_score
                      : null;
                  const display =
                    view === 'rank'
                      ? rankMap.has(model.model_key) ? '#' + rankMap.get(model.model_key) : '—'
                      : view === 'delta'
                        ? delta == null ? '—' : delta === 0 ? 'best' : delta.toFixed(1)
                        : score(scoreValue);
                  const hovered = hoveredModel === model.model_signature;
                  const selected = selectedModel === model.model_signature;
                  const dimmed = Boolean(hoveredModel && !hovered);
                  const showValue =
                    hovered ||
                    selected ||
                    row.winner_model_key === model.model_key ||
                    models.length <= 4;
                  return scoreValue == null ? null : (
                    <div
                      key={model.model_signature}
                      className={
                        'dataset-landscape-point ' +
                        (selected ? 'selected ' : '') +
                        (hovered ? 'hovered ' : '') +
                        (dimmed ? 'dimmed' : '')
                      }
                      style={{
                        left: Math.max(0, Math.min(100, scoreValue)) + '%',
                        top: ((modelIndex + 1) / (models.length + 1)) * 100 + '%',
                      }}
                      title={model.model_key + ' · ' + display}
                      role="button"
                      tabIndex={0}
                      onMouseEnter={() => onHover?.(model.model_signature)}
                      onMouseLeave={() => onHover?.(null)}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        onSelect?.(model.model_signature);
                      }}
                    >
                      <ModelMarker signature={model.model_signature} size={10} />
                      {showValue ? <span>{display}</span> : null}
                    </div>
                  );
                })}
              </div>
              <ChevronRight size={14}/>
            </AppLink>
          );
        })}
      </div>
    </section>
  );
}

export function DatasetDeltaSlopegraph({
  datasets,
  modelA,
  modelB,
}: {
  datasets: DecisionDatasetSummary[];
  modelA: DecisionModelSummary;
  modelB: DecisionModelSummary;
}) {
  const pairs = datasets
    .filter((row) => row.model_key === modelA.model_key)
    .map((a) => {
      const b = datasets.find(
        (row) =>
          row.model_key === modelB.model_key &&
          row.capability_id === a.capability_id &&
          row.dataset_id === a.dataset_id,
      );
      if (a.normalized_quality_score == null || b?.normalized_quality_score == null) {
        return null;
      }
      return {
        capability_id: a.capability_id,
        dataset_id: a.dataset_id,
        a: Number(a.normalized_quality_score),
        b: Number(b.normalized_quality_score),
        delta: Number(a.normalized_quality_score) - Number(b.normalized_quality_score),
      };
    })
    .filter((item): item is NonNullable<typeof item> => item != null)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  const aWins = pairs.filter((pair) => pair.delta > 0.05).length;
  const bWins = pairs.filter((pair) => pair.delta < -0.05).length;
  const ties = pairs.filter((pair) => Math.abs(pair.delta) <= 0.05).length;
  const y = (value: number) => 7 + ((100 - value) / 60) * 30;

  return (
    <section className="analysis-card dataset-slope-card">
      <div className="section-heading">
        <div>
          <h2>Dataset delta slopegraph</h2>
          <p>Sorted by absolute gap. Each row shows where Model A gains or loses against Model B.</p>
        </div>
        <div className="slope-summary">
          <span><b>{aWins}</b> A wins</span>
          <span><b>{bWins}</b> B wins</span>
          <span><b>{ties}</b> ties</span>
        </div>
      </div>
      {pairs.length ? (
        <>
          <div className="slopegraph-column-head">
            <span>Dataset</span>
            <div><strong>{modelShortLabel(modelA.model_key)}</strong><small>Model A</small></div>
            <div><strong>{modelShortLabel(modelB.model_key)}</strong><small>Model B</small></div>
            <span>Δ A − B</span>
          </div>
          <div className="slopegraph-rows">
            {pairs.map((pair) => {
              const state =
                Math.abs(pair.delta) <= 0.05
                  ? 'tie'
                  : pair.delta > 0
                    ? 'a-win'
                    : 'b-win';
              return (
                <div
                  key={pair.capability_id + pair.dataset_id}
                  className={'slopegraph-row ' + state}
                >
                  <div className="slope-dataset-meta">
                    <strong>{pair.dataset_id}</strong>
                    <small>{pair.capability_id.replaceAll('-', ' ')}</small>
                  </div>
                  <div className="slope-mini">
                    <svg viewBox="0 0 420 44" role="img" aria-label={pair.dataset_id}>
                      <line className="slope-midline" x1="20" x2="400" y1="22" y2="22"/>
                      <line
                        className="slope-segment"
                        x1="24"
                        y1={y(pair.a)}
                        x2="396"
                        y2={y(pair.b)}
                      />
                      <circle className="slope-point-a" cx="24" cy={y(pair.a)} r="5"/>
                      <circle className="slope-point-b" cx="396" cy={y(pair.b)} r="5"/>
                      <text x="36" y={y(pair.a) + 3}>{score(pair.a)}</text>
                      <text x="384" y={y(pair.b) + 3} textAnchor="end">{score(pair.b)}</text>
                      <title>
                        {pair.dataset_id + ' · A ' + score(pair.a) + ' · B ' + score(pair.b)}
                      </title>
                    </svg>
                  </div>
                  <em className={state}>
                    {pair.delta > 0 ? '+' : ''}{pair.delta.toFixed(1)}
                  </em>
                </div>
              );
            })}
          </div>
          <div className="slope-legend">
            <span className="a-win">A advantage</span>
            <span className="b-win">B advantage</span>
            <span className="tie">Near tie</span>
          </div>
        </>
      ) : (
        <div className="empty-visual">No common dataset evidence for the selected models.</div>
      )}
    </section>
  );
}

function performanceBand(value: number | null): string {
  if (value == null) return 'unavailable';
  if (value < 40) return 'poor';
  if (value < 60) return 'weak';
  if (value < 80) return 'good';
  return 'excellent';
}

export function DatasetHeatmap({
  datasets,
  models,
  view = 'score',
  selectedModel,
  hoveredModel,
  onSelect,
  onHover,
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
  view?: 'score' | 'delta' | 'rank';
  selectedModel?: string | null;
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onHover?: (modelSignature: string | null) => void;
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
      <div className="performance-legend">
        <span><i className="performance-poor" /> Poor &lt;40</span>
        <span><i className="performance-weak" /> Weak 40–59</span>
        <span><i className="performance-good" /> Good 60–79</span>
        <span><i className="performance-excellent" /> Excellent 80–100</span>
        <span><i className="performance-unavailable" /> No comparable result</span>
      </div>
      <div className="heatmap-scroll">
        <div
          className="heatmap-grid"
          style={{ '--model-count': modelKeys.length } as CSSProperties}
        >
          <div className="heatmap-head">Capability / dataset</div>
          <div className="heatmap-head samples">n</div>
          {models.map((model) => (
            <div
              className={
                'heatmap-head model ' +
                (selectedModel === model.model_signature ? 'selected ' : '') +
                (hoveredModel && hoveredModel !== model.model_signature ? 'dimmed' : '')
              }
              key={model.model_signature}
              role="button"
              tabIndex={0}
              onMouseEnter={() => onHover?.(model.model_signature)}
              onMouseLeave={() => onHover?.(null)}
              onClick={() => onSelect?.(model.model_signature)}
            >
              <span><ModelMarker signature={model.model_signature} /> {model.model_key}</span>
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
                  const model = models.find((item) => item.model_key === modelKey);
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
                  const isWinner = value != null && best != null && value === best;
                  const signature = model?.model_signature ?? modelKey;
                  const dimmed = Boolean(
                    hoveredModel && hoveredModel !== signature,
                  );
                  return (
                    <div
                      key={modelKey}
                      className={
                        'heatmap-cell performance-' + performanceBand(value) + ' ' +
                        (isWinner ? 'winner ' : '') +
                        (selectedModel === signature ? 'selected ' : '') +
                        (dimmed ? 'dimmed' : '')
                      }
                      onMouseEnter={() => onHover?.(signature)}
                      onMouseLeave={() => onHover?.(null)}
                      onClick={() => onSelect?.(signature)}
                      title={
                        cell
                          ? [
                              modelKey,
                              'score ' + score(value),
                              'P50 ' + milliseconds(cell.latency_p50_ms),
                              cell.provider_cost_known
                                ? usd(cell.provider_cost_per_1k_cases_usd) +
                                  ' / 1k cases · ' +
                                  providerCostCoverage(
                                    cell.provider_cost_status,
                                    cell.provider_cost_priced_cases,
                                    cell.provider_cost_total_cases,
                                    cell.provider_cost_coverage_rate,
                                  )
                                : providerCostCoverage(
                                    cell.provider_cost_status,
                                    cell.provider_cost_priced_cases,
                                    cell.provider_cost_total_cases,
                                    cell.provider_cost_coverage_rate,
                                  ),
                            ].join(' · ')
                          : 'No CURRENT comparable result'
                      }
                    >
                      {isWinner && view === 'score' ? <span className="cell-winner">★</span> : null}
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
