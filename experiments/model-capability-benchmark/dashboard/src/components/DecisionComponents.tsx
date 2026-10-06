import {
  Activity,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Flame,
  Info,
  Maximize2,
  RotateCcw,
  Sparkles,
  Trophy,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
  selectedModels,
  hoveredModel,
  onSelect,
  onToggleSelect,
  onHover,
}: {
  title: string;
  description: string;
  models: DecisionModelSummary[];
  xMetric: 'latency' | 'cost';
  selectedModel?: string | null;
  selectedModels?: string[];
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onToggleSelect?: (modelSignature: string, isMultiToggle: boolean) => void;
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

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    model: DecisionModelSummary;
    quality: number;
    xValue: number;
  } | null>(null);

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
        <div className="scatter-canvas-shell" style={{ position: 'relative' }}>
          <svg
            className="scatter-svg"
            viewBox="0 0 600 330"
            role="img"
            aria-label={title}
            onMouseLeave={() => setTooltip(null)}
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
              const isSelected = selectedModels && selectedModels.length > 0
                ? selectedModels.includes(model.model_signature)
                : selectedModel === model.model_signature;
              const hovered = hoveredModel === model.model_signature || tooltip?.model.model_signature === model.model_signature;
              const dimmed = Boolean(hoveredModel && !hovered);
              const showLabel = expanded || isSelected || hovered || frontier || plotted.length <= 6;
              const labelRight = x < 410;
              const labelY = y + (index % 2 === 0 ? -10 : 15);
              return (
                <g
                  key={model.model_signature}
                  className={
                    'scatter-point ' +
                    (isSelected ? 'selected ' : '') +
                    (hovered ? 'hovered ' : '') +
                    (dimmed ? 'dimmed ' : '') +
                    (frontier ? 'frontier ' : '') +
                    (xMetric === 'cost' && model.provider_cost_status === 'partial'
                      ? 'cost-partial'
                      : '')
                  }
                  onClick={(event) => {
                    const isMultiToggle = event.shiftKey || event.metaKey || event.ctrlKey;
                    if (onToggleSelect) {
                      onToggleSelect(model.model_signature, isMultiToggle);
                    } else if (onSelect) {
                      onSelect(model.model_signature);
                    }
                  }}
                  onMouseEnter={(event) => {
                    onHover?.(model.model_signature);
                    const rect = event.currentTarget.closest('.scatter-canvas-shell')?.getBoundingClientRect();
                    if (rect) {
                      setTooltip({
                        x: event.clientX - rect.left,
                        y: event.clientY - rect.top,
                        model,
                        quality,
                        xValue,
                      });
                    }
                  }}
                  onMouseMove={(event) => {
                    const rect = event.currentTarget.closest('.scatter-canvas-shell')?.getBoundingClientRect();
                    if (rect) {
                      setTooltip((prev) => prev ? {
                        ...prev,
                        x: event.clientX - rect.left,
                        y: event.clientY - rect.top,
                      } : null);
                    }
                  }}
                  onMouseLeave={() => {
                    onHover?.(null);
                    setTooltip(null);
                  }}
                >
                  <circle
                    cx={x}
                    cy={y}
                    r={isSelected || hovered ? 8 : 6}
                    style={{ fill: visual.color }}
                  />
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

          {tooltip ? (
            <div
              className="chart-dot-tooltip"
              style={{
                left: tooltip.x,
                top: tooltip.y,
              }}
            >
              <div className="dot-tooltip-header">
                <span
                  className="dot-tooltip-badge"
                  style={{ background: modelVisual(tooltip.model.model_signature).color }}
                />
                <strong className="dot-tooltip-title">{tooltip.model.model_key}</strong>
              </div>
              <div className="dot-tooltip-body">
                <div className="dot-tooltip-row">
                  <span className="dot-tooltip-label">Quality Score</span>
                  <span className="dot-tooltip-val highlight">{tooltip.quality.toFixed(1)}</span>
                </div>
                <div className="dot-tooltip-row">
                  <span className="dot-tooltip-label">
                    {xMetric === 'latency' ? 'P50 Latency' : 'Cost / 1k cases'}
                  </span>
                  <span className="dot-tooltip-val">
                    {xMetric === 'latency'
                      ? milliseconds(tooltip.xValue)
                      : usd(tooltip.xValue)}
                  </span>
                </div>
                {tooltip.model.deployment ? (
                  <div className="dot-tooltip-row">
                    <span className="dot-tooltip-label">Deployment</span>
                    <span className="dot-tooltip-val capitalize">{tooltip.model.deployment}</span>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
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
          selectedModels={selectedModels}
          onHover={onHover}
          onSelect={onSelect}
          onToggleSelect={onToggleSelect}
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
                  selectedModels={selectedModels}
                  onHover={onHover}
                  onSelect={onSelect}
                  onToggleSelect={onToggleSelect}
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
  selectedModels,
  hoveredModel,
  onSelect,
  onToggleSelect,
  onHover,
}: {
  models: DecisionModelSummary[];
  selectedModel?: string | null;
  selectedModels?: string[];
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onToggleSelect?: (modelSignature: string, isMultiToggle: boolean) => void;
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
  const splitIndex = Math.ceil(ranked.length / 2);
  const columns = [ranked.slice(0, splitIndex), ranked.slice(splitIndex)];

  const renderRow = (model: DecisionModelSummary, index: number) => {
    const isSelected = selectedModels && selectedModels.length > 0
      ? selectedModels.includes(model.model_signature)
      : selectedModel === model.model_signature;
    return (
      <button
        type="button"
        key={model.model_signature}
        className={
          'leader-row ' +
          (isSelected ? 'selected ' : '') +
          (hoveredModel && hoveredModel !== model.model_signature ? 'dimmed' : '')
        }
        onClick={(event) => {
          const isMultiToggle = event.shiftKey || event.metaKey || event.ctrlKey;
          if (onToggleSelect) {
            onToggleSelect(model.model_signature, isMultiToggle);
          } else if (onSelect) {
            onSelect(model.model_signature);
          }
        }}
        onMouseEnter={() => onHover?.(model.model_signature)}
        onMouseLeave={() => onHover?.(null)}
      >
      <span className="rank">{index + 1}</span>
      <span className="leader-name">
        <strong><ModelMarker signature={model.model_signature} /> {model.model_key}</strong>
        <span>
          <DeploymentBadge deployment={model.deployment} />
          {!model.quality_coverage_complete ? <em>Partial coverage</em> : null}
        </span>
      </span>
      <span className="leader-bar">
        <i
          style={{
            width: ((model.overall_quality_score ?? 0) / max) * 100 + '%',
            background: modelVisual(model.model_signature).color,
          }}
        />
      </span>
      <strong className="leader-score">{score(model.overall_quality_score)}</strong>
    </button>
  );
};

  return (
    <section className="analysis-card leaderboard-card">
      <div className="section-heading compact leaderboard-heading">
        <div>
          <h2>Overall quality</h2>
          <p>Equal-weight score across the selected comparable capability cohort.</p>
        </div>
        <div className="leaderboard-heading-meta">
          <span className="semantic-chip">{ranked.length} models</span>
          <span className="semantic-chip">policy v1</span>
        </div>
      </div>
      <div className="leaderboard-columns">
        {columns.map((column, columnIndex) => (
          <div className="leaderboard-column" key={columnIndex}>
            {column.map((model, localIndex) =>
              renderRow(model, columnIndex === 0 ? localIndex : splitIndex + localIndex),
            )}
          </div>
        ))}
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
  selectedModels,
  hoveredModel,
  onSelect,
  onToggleSelect,
  onHover,
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
  view?: 'score' | 'delta' | 'rank';
  selectedModel?: string | null;
  selectedModels?: string[];
  hoveredModel?: string | null;
  onSelect?: (modelSignature: string) => void;
  onToggleSelect?: (modelSignature: string, isMultiToggle: boolean) => void;
  onHover?: (modelSignature: string | null) => void;
}) {
  const [activeView, setActiveView] = useState<'score' | 'delta' | 'rank'>(view);
  const [expanded, setExpanded] = useState(false);
  const [modelSort, setModelSort] = useState<'quality' | 'name' | 'deployment' | 'latency' | 'original'>('quality');
  const [sortColumn, setSortColumn] = useState<string>('dataset');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const scrollRef = useRef<HTMLDivElement>(null);
  const modalScrollRef = useRef<HTMLDivElement>(null);

  // Synchronize internal activeView when prop view changes
  useEffect(() => {
    setActiveView(view);
  }, [view]);

  // Dynamic ordering of model columns
  const orderedModels = useMemo(() => {
    const list = [...models];
    if (modelSort === 'quality') {
      return list.sort(
        (a, b) => (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1),
      );
    }
    if (modelSort === 'name') {
      return list.sort((a, b) => a.model_key.localeCompare(b.model_key));
    }
    if (modelSort === 'deployment') {
      return list.sort((a, b) => {
        if (a.deployment !== b.deployment) {
          return a.deployment === 'local' ? -1 : 1;
        }
        return (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1);
      });
    }
    if (modelSort === 'latency') {
      return list.sort((a, b) => {
        if (a.latency_p50_ms == null && b.latency_p50_ms == null) return 0;
        if (a.latency_p50_ms == null) return 1;
        if (b.latency_p50_ms == null) return -1;
        return Number(a.latency_p50_ms) - Number(b.latency_p50_ms);
      });
    }
    return list;
  }, [models, modelSort]);

  const modelKeys = useMemo(() => orderedModels.map((model) => model.model_key), [orderedModels]);

  const modelsMap = useMemo(() => {
    const map = new Map<string, DecisionModelSummary>();
    models.forEach((model) => map.set(model.model_key, model));
    return map;
  }, [models]);

  const localKeys = useMemo(
    () =>
      new Set(
        models.filter((model) => model.deployment === 'local').map((model) => model.model_key),
      ),
    [models],
  );

  const baseRows = useMemo(() => {
    const grouped = new Map<string, DecisionDatasetSummary[]>();
    datasets.forEach((row) => {
      const key = row.capability_id + '::' + row.dataset_id;
      grouped.set(key, [...(grouped.get(key) ?? []), row]);
    });

    return [...grouped.entries()].map(([key, cells]) => {
      const [capability_id, dataset_id] = key.split('::');
      const scored = cells.filter((c) => c.normalized_quality_score != null);
      const sorted = [...scored].sort(
        (a, b) => Number(b.normalized_quality_score) - Number(a.normalized_quality_score),
      );
      const scores = scored.map((c) => Number(c.normalized_quality_score));
      const best = scores.length ? Math.max(...scores) : null;
      const worst = scores.length ? Math.min(...scores) : null;
      const spread = best != null && worst != null ? best - worst : null;
      const avg = scores.length ? scores.reduce((sum, v) => sum + v, 0) / scores.length : null;
      const winner = sorted[0]?.model_key ?? null;
      const winnerScore = sorted[0]?.normalized_quality_score ?? null;
      const local = sorted.find((c) => localKeys.has(c.model_key));

      return {
        capability_id,
        dataset_id,
        sample_count: cells[0]?.sample_count ?? 0,
        winner_model_key: winner,
        winner_score: winnerScore,
        worst_score: worst,
        spread,
        average_score: avg,
        best_local_model_key: local?.model_key ?? null,
      };
    });
  }, [datasets, localKeys]);

  const mostWins = useMemo(() => {
    const wins = new Map<string, number>();
    baseRows.forEach((row) => {
      if (row.winner_model_key) {
        wins.set(row.winner_model_key, (wins.get(row.winner_model_key) ?? 0) + 1);
      }
    });
    return [...wins.entries()].sort((a, b) => b[1] - a[1])[0] ?? null;
  }, [baseRows]);

  const bestLocal = useMemo(() => {
    const localWins = new Map<string, number>();
    baseRows.forEach((row) => {
      if (row.best_local_model_key) {
        localWins.set(
          row.best_local_model_key,
          (localWins.get(row.best_local_model_key) ?? 0) + 1,
        );
      }
    });
    return [...localWins.entries()].sort((a, b) => b[1] - a[1])[0] ?? null;
  }, [baseRows]);

  const hardest = useMemo(
    () =>
      [...baseRows]
        .filter((row) => row.average_score != null)
        .sort((a, b) => Number(a.average_score) - Number(b.average_score))[0] ?? null,
    [baseRows],
  );

  const discriminative = useMemo(
    () =>
      [...baseRows]
        .filter((row) => row.spread != null)
        .sort((a, b) => Number(b.spread) - Number(a.spread))[0] ?? null,
    [baseRows],
  );

  const byCell = useMemo(
    () =>
      new Map(
        datasets.map((row) => [
          row.model_key + '::' + row.capability_id + '::' + row.dataset_id,
          row,
        ]),
      ),
    [datasets],
  );

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection(column === 'dataset' ? 'asc' : 'desc');
    }
  };

  const sortedRows = useMemo(() => {
    return [...baseRows].sort((a, b) => {
      if (sortColumn === 'dataset') {
        const keyA = a.capability_id + ' ' + a.dataset_id;
        const keyB = b.capability_id + ' ' + b.dataset_id;
        return sortDirection === 'asc' ? keyA.localeCompare(keyB) : keyB.localeCompare(keyA);
      }
      if (sortColumn === 'samples') {
        return sortDirection === 'asc'
          ? a.sample_count - b.sample_count
          : b.sample_count - a.sample_count;
      }
      if (sortColumn === 'winner') {
        const keyA = a.winner_model_key ?? '';
        const keyB = b.winner_model_key ?? '';
        return sortDirection === 'asc' ? keyA.localeCompare(keyB) : keyB.localeCompare(keyA);
      }
      if (sortColumn === 'spread') {
        const valA = a.spread ?? -1;
        const valB = b.spread ?? -1;
        return sortDirection === 'asc' ? valA - valB : valB - valA;
      }
      // Sort by specific model score
      const cellA = byCell.get(sortColumn + '::' + a.capability_id + '::' + a.dataset_id);
      const cellB = byCell.get(sortColumn + '::' + b.capability_id + '::' + b.dataset_id);
      const valA = cellA?.normalized_quality_score ?? null;
      const valB = cellB?.normalized_quality_score ?? null;
      if (valA == null && valB == null) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;
      return sortDirection === 'asc' ? valA - valB : valB - valA;
    });
  }, [baseRows, sortColumn, sortDirection, byCell]);

  // Translate vertical mouse wheel to horizontal scroll for convenient desktop mouse navigation
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && el.scrollWidth > el.clientWidth) {
        const canScrollLeft = el.scrollLeft > 0 && e.deltaY < 0;
        const canScrollRight = el.scrollLeft + el.clientWidth < el.scrollWidth - 1 && e.deltaY > 0;
        if (canScrollLeft || canScrollRight) {
          e.preventDefault();
          el.scrollLeft += e.deltaY;
        }
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    const el = modalScrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && el.scrollWidth > el.clientWidth) {
        const canScrollLeft = el.scrollLeft > 0 && e.deltaY < 0;
        const canScrollRight = el.scrollLeft + el.clientWidth < el.scrollWidth - 1 && e.deltaY > 0;
        if (canScrollLeft || canScrollRight) {
          e.preventDefault();
          el.scrollLeft += e.deltaY;
        }
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [expanded]);

  const scrollLeft = () => {
    scrollRef.current?.scrollBy({ left: -240, behavior: 'smooth' });
  };
  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 240, behavior: 'smooth' });
  };

  const renderTable = (refTarget: React.RefObject<HTMLDivElement | null>) => (
    <div className="heatmap-scroll" ref={refTarget}>
      <div
        className="heatmap-grid"
        style={{ '--model-count': modelKeys.length } as CSSProperties}
      >
        <div
          className={
            'heatmap-head sticky-col-1 sortable ' +
            (sortColumn === 'dataset' ? 'active-sort ' : '')
          }
          role="button"
          tabIndex={0}
          onClick={() => handleSort('dataset')}
          title="Click to sort rows alphabetically by dataset name"
        >
          <span>Capability / dataset</span>
          <span className="sort-icon-wrap">
            {sortColumn === 'dataset' ? (
              sortDirection === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
            ) : (
              <ArrowUpDown size={11} className="sort-hint" />
            )}
          </span>
        </div>
        <div
          className={
            'heatmap-head samples sticky-col-2 sortable ' +
            (sortColumn === 'samples' ? 'active-sort ' : '')
          }
          role="button"
          tabIndex={0}
          onClick={() => handleSort('samples')}
          title="Click to sort rows by sample count (n)"
        >
          <span>n</span>
          <span className="sort-icon-wrap">
            {sortColumn === 'samples' ? (
              sortDirection === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />
            ) : (
              <ArrowUpDown size={10} className="sort-hint" />
            )}
          </span>
        </div>
        <div
          className={
            'heatmap-head winner sortable ' +
            (sortColumn === 'winner' ? 'active-sort ' : '')
          }
          role="button"
          tabIndex={0}
          onClick={() => handleSort('winner')}
          title="Click to sort rows by winner model"
        >
          <span>Winner 🏆</span>
          <span className="sort-icon-wrap">
            {sortColumn === 'winner' ? (
              sortDirection === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />
            ) : (
              <ArrowUpDown size={10} className="sort-hint" />
            )}
          </span>
        </div>
        <div
          className={
            'heatmap-head spread sortable ' +
            (sortColumn === 'spread' ? 'active-sort ' : '')
          }
          role="button"
          tabIndex={0}
          onClick={() => handleSort('spread')}
          title="Click to sort rows by spread (discrimination gap)"
        >
          <span>Spread Δ</span>
          <span className="sort-icon-wrap">
            {sortColumn === 'spread' ? (
              sortDirection === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />
            ) : (
              <ArrowUpDown size={10} className="sort-hint" />
            )}
          </span>
        </div>
        {orderedModels.map((model) => {
          const isSorted = sortColumn === model.model_key;
          const isSelected = selectedModels && selectedModels.length > 0
            ? selectedModels.includes(model.model_signature)
            : selectedModel === model.model_signature;
          return (
            <div
              className={
                'heatmap-head model sortable ' +
                (isSelected ? 'selected ' : '') +
                (hoveredModel && hoveredModel !== model.model_signature ? 'dimmed ' : '') +
                (isSorted ? 'active-sort ' : '')
              }
              key={model.model_signature}
              role="button"
              tabIndex={0}
              onMouseEnter={() => onHover?.(model.model_signature)}
              onMouseLeave={() => onHover?.(null)}
              onClick={(event) => {
                const isMultiToggle = event.shiftKey || event.metaKey || event.ctrlKey;
                handleSort(model.model_key);
                if (onToggleSelect) {
                  onToggleSelect(model.model_signature, isMultiToggle);
                } else if (onSelect) {
                  onSelect(model.model_signature);
                }
              }}
              title={'Click to sort rows by ' + model.model_key + ' score (' + (isSorted && sortDirection === 'desc' ? 'descending' : 'ascending') + ') · Shift/Cmd+Click to toggle selection'}
            >
              <div className="heatmap-model-name">
                <span title={model.model_key}>
                  <ModelMarker signature={model.model_signature} /> {modelShortLabel(model.model_key)}
                </span>
                <span className="sort-icon-wrap">
                  {isSorted ? (
                    sortDirection === 'desc' ? <ArrowDown size={12} /> : <ArrowUp size={12} />
                  ) : (
                    <ArrowUpDown size={11} className="sort-hint" />
                  )}
                </span>
              </div>
              <DeploymentBadge deployment={model.deployment} />
            </div>
          );
        })}
        {sortedRows.map((row) => {
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
                className="heatmap-label sticky-col-1"
              >
                <span>{row.capability_id.replaceAll('-', ' ')}</span>
                <strong>{row.dataset_id}</strong>
                <ChevronRight size={14} />
              </AppLink>
              <div className="heatmap-samples sticky-col-2">{row.sample_count}</div>
              <div
                className="heatmap-winner"
                title={
                  row.winner_model_key
                    ? `Top score: ${row.winner_score?.toFixed(1)}% by ${row.winner_model_key}`
                    : '—'
                }
              >
                {row.winner_model_key ? (
                  <>
                    <ModelMarker
                      signature={
                        modelsMap.get(row.winner_model_key)?.model_signature ??
                        row.winner_model_key
                      }
                      size={10}
                    />
                    <span className="winner-name">
                      {modelShortLabel(row.winner_model_key)}
                    </span>
                    <span className="winner-score">
                      ({row.winner_score?.toFixed(1)}%)
                    </span>
                  </>
                ) : (
                  <span className="muted">—</span>
                )}
              </div>
              <div
                className={
                  'heatmap-spread ' +
                  (row.spread != null && row.spread > 40 ? 'high-spread' : '')
                }
                title={
                  row.spread != null
                    ? `Gap between best and worst model: Δ ${row.spread.toFixed(1)} pt`
                    : '—'
                }
              >
                {row.spread != null ? `Δ ${row.spread.toFixed(1)}` : '—'}
              </div>
              {modelKeys.map((modelKey) => {
                const model = orderedModels.find((item) => item.model_key === modelKey);
                const cell = byCell.get(
                  modelKey + '::' + row.capability_id + '::' + row.dataset_id,
                );
                const value = cell?.normalized_quality_score ?? null;
                const delta =
                  value != null && best != null ? value - best : null;
                const display =
                  activeView === 'rank'
                    ? cell
                      ? '#' + rankMap.get(modelKey)
                      : '—'
                    : activeView === 'delta'
                      ? delta == null
                        ? '—'
                        : delta === 0
                          ? 'best'
                          : delta.toFixed(1)
                      : score(value);
                const isWinner = value != null && best != null && value === best;
                const signature = model?.model_signature ?? modelKey;
                const isSelected = selectedModels && selectedModels.length > 0
                  ? selectedModels.includes(signature)
                  : selectedModel === signature;
                const dimmed = Boolean(
                  hoveredModel && hoveredModel !== signature,
                );
                return (
                  <div
                    key={modelKey}
                    className={
                      'heatmap-cell performance-' + performanceBand(value) + ' ' +
                      (isWinner ? 'winner ' : '') +
                      (isSelected ? 'selected ' : '') +
                      (dimmed ? 'dimmed' : '')
                    }
                    onMouseEnter={() => onHover?.(signature)}
                    onMouseLeave={() => onHover?.(null)}
                    onClick={(event) => {
                      const isMultiToggle = event.shiftKey || event.metaKey || event.ctrlKey;
                      if (onToggleSelect) {
                        onToggleSelect(signature, isMultiToggle);
                      } else if (onSelect) {
                        onSelect(signature);
                      }
                    }}
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
                    {isWinner && activeView === 'score' ? <span className="cell-winner">★</span> : null}
                    {display}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      <section className="analysis-card heatmap-card">
        <div className="section-heading compact heatmap-header-row">
          <div>
            <h2>Performance by dataset</h2>
            <p>Per-dataset winners, score spreads (Δ), and granular quality comparisons.</p>
          </div>
          <div className="heatmap-actions">
            <div className="segmented">
              {(['score', 'delta', 'rank'] as const).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={activeView === item ? 'active' : ''}
                  onClick={() => setActiveView(item)}
                >
                  {item === 'score' ? 'Score' : item === 'delta' ? 'Delta' : 'Rank'}
                </button>
              ))}
            </div>

            <select
              className="heatmap-sort-select"
              value={modelSort}
              onChange={(event) =>
                setModelSort(
                  event.target.value as 'quality' | 'name' | 'deployment' | 'latency' | 'original',
                )
              }
              title="Sort model columns (horizontal order)"
            >
              <option value="quality">Models: Overall Quality ↓</option>
              <option value="name">Models: Name (A → Z)</option>
              <option value="deployment">Models: Local first</option>
              <option value="latency">Models: Fastest P50</option>
              <option value="original">Models: Default order</option>
            </select>

            <div className="heatmap-scroll-controls" title="Scroll horizontally">
              <button
                type="button"
                className="heatmap-scroll-btn"
                onClick={scrollLeft}
                title="Scroll left"
                aria-label="Scroll left"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                type="button"
                className="heatmap-scroll-btn"
                onClick={scrollRight}
                title="Scroll right"
                aria-label="Scroll right"
              >
                <ChevronRight size={15} />
              </button>
            </div>
            <button
              type="button"
              className="expand-chart-button"
              onClick={() => setExpanded(true)}
              title="Expand dataset matrix"
            >
              <Maximize2 size={15} />
            </button>
          </div>
        </div>

        <div className="dataset-insight-chips">
          <div className="insight-chip-item">
            <div className="insight-chip-icon trophy"><Trophy size={16} /></div>
            <div className="insight-chip-content">
              <span>Most dataset wins</span>
              <strong>
                {mostWins
                  ? `${modelShortLabel(mostWins[0])} · ${mostWins[1]} ${mostWins[1] === 1 ? 'win' : 'wins'}`
                  : '—'}
              </strong>
            </div>
          </div>

          <div className="insight-chip-item">
            <div className="insight-chip-icon local"><Zap size={16} /></div>
            <div className="insight-chip-content">
              <span>Best local model</span>
              <strong>
                {bestLocal
                  ? `${modelShortLabel(bestLocal[0])} · ${bestLocal[1]} ${bestLocal[1] === 1 ? 'win' : 'wins'}`
                  : '—'}
              </strong>
            </div>
          </div>

          <div className="insight-chip-item">
            <div className="insight-chip-icon hardest"><Flame size={16} /></div>
            <div className="insight-chip-content">
              <span>Hardest dataset</span>
              <strong>
                {hardest
                  ? `${hardest.dataset_id} (avg ${hardest.average_score?.toFixed(1) ?? '—'}%)`
                  : '—'}
              </strong>
            </div>
          </div>

          <div className="insight-chip-item">
            <div className="insight-chip-icon discriminative"><Activity size={16} /></div>
            <div className="insight-chip-content">
              <span>Widest spread</span>
              <strong>
                {discriminative
                  ? `${discriminative.dataset_id} (Δ ${discriminative.spread?.toFixed(1) ?? '—'} pt)`
                  : '—'}
              </strong>
            </div>
          </div>
        </div>

        <div className="heatmap-status-bar">
          <div className="performance-legend">
            <span><i className="performance-poor" /> Poor &lt;40</span>
            <span><i className="performance-weak" /> Weak 40–59</span>
            <span><i className="performance-good" /> Good 60–79</span>
            <span><i className="performance-excellent" /> Excellent 80–100</span>
            <span><i className="performance-unavailable" /> No comparable result</span>
          </div>
          {sortColumn !== 'dataset' || sortDirection !== 'asc' ? (
            <div className="heatmap-sort-pill">
              <span>
                Sorted by:{' '}
                <strong>
                  {sortColumn === 'dataset'
                    ? 'Dataset name'
                    : sortColumn === 'samples'
                      ? 'Sample count (n)'
                      : sortColumn === 'winner'
                        ? 'Winner model'
                        : sortColumn === 'spread'
                          ? 'Score spread (Δ)'
                          : sortColumn}
                </strong>{' '}
                ({sortDirection === 'desc' ? 'descending' : 'ascending'})
              </span>
              <button
                type="button"
                className="heatmap-sort-reset"
                onClick={() => {
                  setSortColumn('dataset');
                  setSortDirection('asc');
                }}
                title="Reset row sorting to default (alphabetical)"
              >
                <RotateCcw size={10} /> Reset
              </button>
            </div>
          ) : null}
        </div>

        {renderTable(scrollRef)}
      </section>

      {expanded ? (
        <div
          className="chart-modal-backdrop"
          role="presentation"
          onMouseDown={() => setExpanded(false)}
        >
          <section
            className="chart-modal heatmap-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Dataset performance matrix"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="chart-modal-header">
              <div>
                <span className="eyebrow">Analytical matrix</span>
                <h2>Performance by dataset</h2>
                <p>Full cross-model comparison across all capabilities and datasets.</p>
              </div>
              <div className="heatmap-modal-header-actions">
                <div className="segmented">
                  {(['score', 'delta', 'rank'] as const).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={activeView === item ? 'active' : ''}
                      onClick={() => setActiveView(item)}
                    >
                      {item === 'score' ? 'Score' : item === 'delta' ? 'Delta' : 'Rank'}
                    </button>
                  ))}
                </div>
                <select
                  className="heatmap-sort-select"
                  value={modelSort}
                  onChange={(event) =>
                    setModelSort(
                      event.target.value as 'quality' | 'name' | 'deployment' | 'latency' | 'original',
                    )
                  }
                  title="Sort model columns (horizontal order)"
                >
                  <option value="quality">Models: Overall Quality ↓</option>
                  <option value="name">Models: Name (A → Z)</option>
                  <option value="deployment">Models: Local first</option>
                  <option value="latency">Models: Fastest P50</option>
                  <option value="original">Models: Default order</option>
                </select>
                <button
                  type="button"
                  className="modal-close"
                  onClick={() => setExpanded(false)}
                >
                  <X size={18} />
                </button>
              </div>
            </header>
            <div className="heatmap-modal-body">
              <div className="heatmap-status-bar">
                <div className="performance-legend">
                  <span><i className="performance-poor" /> Poor &lt;40</span>
                  <span><i className="performance-weak" /> Weak 40–59</span>
                  <span><i className="performance-good" /> Good 60–79</span>
                  <span><i className="performance-excellent" /> Excellent 80–100</span>
                  <span><i className="performance-unavailable" /> No comparable result</span>
                </div>
                {sortColumn !== 'dataset' || sortDirection !== 'asc' ? (
                  <div className="heatmap-sort-pill">
                    <span>
                      Sorted by:{' '}
                      <strong>
                        {sortColumn === 'dataset'
                          ? 'Dataset name'
                          : sortColumn === 'samples'
                            ? 'Sample count (n)'
                            : sortColumn === 'winner'
                              ? 'Winner model'
                              : sortColumn === 'spread'
                                ? 'Score spread (Δ)'
                                : sortColumn}
                      </strong>{' '}
                      ({sortDirection === 'desc' ? 'descending' : 'ascending'})
                    </span>
                    <button
                      type="button"
                      className="heatmap-sort-reset"
                      onClick={() => {
                        setSortColumn('dataset');
                        setSortDirection('asc');
                      }}
                      title="Reset row sorting to default (alphabetical)"
                    >
                      <RotateCcw size={10} /> Reset
                    </button>
                  </div>
                ) : null}
              </div>
              {renderTable(modalScrollRef)}
            </div>
          </section>
        </div>
      ) : null}
    </>
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
