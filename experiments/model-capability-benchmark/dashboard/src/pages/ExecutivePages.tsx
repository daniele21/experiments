import {
  BadgeDollarSign,
  Database,
  HardDrive,
  Layers3,
  ShieldCheck,
  Sparkles,
  Trophy,
  Zap,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import decisioRuntimeLogo from '../assets/runtime/decisio.webp';
import korgisRuntimeLogo from '../assets/runtime/korgis.webp';
import { overview } from '../data';
import type {
  DecisionCapabilitySummary,
  DecisionDatasetSummary,
  DecisionModelSummary,
} from '../types';
import { AppLink } from '../components/Shell';

export type ExecutiveView =
  | 'quality'
  | 'speed'
  | 'size'
  | 'cost'
  | 'capabilities'
  | 'dataset-fit'
  | 'reliability';

const EXECUTIVE_VIEWS: Array<{
  id: ExecutiveView;
  label: string;
  href: string;
}> = [
  { id: 'quality', label: 'Quality', href: '/executive/quality' },
  { id: 'speed', label: 'Speed', href: '/executive/speed' },
  { id: 'size', label: 'Size', href: '/executive/size' },
  { id: 'cost', label: 'Cost', href: '/executive/cost' },
  { id: 'capabilities', label: 'Capabilities', href: '/executive/capabilities' },
  { id: 'dataset-fit', label: 'Model × Dataset', href: '/executive/dataset-fit' },
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

function modelSizeValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const gib = value / (1024 ** 3);
  if (gib >= 1) return `${gib.toFixed(gib < 10 ? 2 : 1)} GB`;
  return `${Math.round(value / (1024 ** 2))} MB`;
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

type RuntimeBrand = 'korgis' | 'decisio';

function runtimeBrand(model: Pick<DecisionModelSummary, 'deployment' | 'runtime_key' | 'provider_key' | 'tags'>): RuntimeBrand | null {
  if (model.deployment !== 'local') return null;
  if (
    model.runtime_key === 'decisio-local' ||
    model.provider_key === 'decisio' ||
    model.tags?.includes('decisio')
  ) {
    return 'decisio';
  }
  if (model.runtime_key === 'korgis-local' || model.provider_key === 'korgis') {
    return 'korgis';
  }
  return null;
}

function RuntimeBadge({
  model,
  compact = false,
}: {
  model: Pick<DecisionModelSummary, 'deployment' | 'runtime_key' | 'provider_key' | 'tags'>;
  compact?: boolean;
}) {
  const brand = runtimeBrand(model);
  if (!brand) return null;
  const label = brand === 'korgis' ? 'Korgis runtime' : 'Decisio runtime';
  return (
    <span className={compact ? 'runtime-brand-badge compact' : 'runtime-brand-badge'} title={label} aria-label={label}>
      <img src={brand === 'korgis' ? korgisRuntimeLogo : decisioRuntimeLogo} alt="" />
      {!compact ? <span>{brand === 'korgis' ? 'Korgis' : 'Decisio'}</span> : null}
    </span>
  );
}

interface QualityRankItem {
  model: DecisionModelSummary;
  score: number;
}

function overallQualityRanking(models: DecisionModelSummary[]): QualityRankItem[] {
  const scored = models.filter((model) => model.overall_quality_score != null);
  const complete = scored.filter((model) => model.quality_coverage_complete);
  return [...(complete.length ? complete : scored)]
    .sort((a, b) => modelQuality(b) - modelQuality(a))
    .map((model) => ({ model, score: modelQuality(model) }));
}

function datasetQualityRanking(
  rows: DecisionDatasetSummary[],
  models: DecisionModelSummary[],
  datasetId: string,
): QualityRankItem[] {
  const modelBySignature = new Map(models.map((model) => [model.model_signature, model]));
  const grouped = new Map<string, { model: DecisionModelSummary; weighted: number; weight: number }>();
  for (const row of rows) {
    if (row.dataset_id !== datasetId || row.normalized_quality_score == null) continue;
    const model = modelBySignature.get(row.model_signature);
    if (!model) continue;
    const weight = Math.max(1, row.observed_case_count || row.sample_count || 1);
    const current = grouped.get(row.model_signature) ?? { model, weighted: 0, weight: 0 };
    current.weighted += Number(row.normalized_quality_score) * weight;
    current.weight += weight;
    grouped.set(row.model_signature, current);
  }
  return [...grouped.values()]
    .map((item) => ({ model: item.model, score: item.weighted / item.weight }))
    .sort((a, b) => b.score - a.score);
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

function QualityBars({ items }: { items: QualityRankItem[] }) {
  if (!items.length) {
    return <ExecutiveEmpty message="Project completed benchmark results to compare quality." />;
  }
  const max = Math.max(...items.map((item) => item.score), 1);
  return (
    <div className="executive-ranking">
      {items.map(({ model, score: value }, index) => (
        <div className={index === 0 ? 'executive-rank-row winner' : 'executive-rank-row'} key={model.model_signature}>
          <span className="executive-rank-number">{index + 1}</span>
          <div className="executive-rank-model">
            <strong>{model.model_key}</strong>
            <span className="executive-rank-meta">
              <span>{model.deployment === 'local' ? 'Local' : 'API'}{model.family ? ` · ${model.family}` : ''}</span>
              <RuntimeBadge model={model} compact />
            </span>
          </div>
          <div className="executive-rank-track">
            <i style={{ width: `${Math.max(2, (value / max) * 100)}%` }} />
          </div>
          <strong className="executive-rank-value">{scoreValue(value)}</strong>
        </div>
      ))}
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
  const [hoveredSignature, setHoveredSignature] = useState<string | null>(null);
  const [selectedSignatures, setSelectedSignatures] = useState<string[]>([]);

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

  const plotted = points.map((point) => ({
    ...point,
    cx: xScale(point.xv),
    cy: yScale(point.yv),
    onPareto: pareto(point.model),
  }));
  const hovered = plotted.find((point) => point.model.model_signature === hoveredSignature) ?? null;

  const executiveTarget = [...plotted]
    .filter((point) => point.onPareto)
    .sort((a, b) => b.yv - a.yv)[0] ?? [...plotted].sort((a, b) => b.yv - a.yv)[0];
  const persistentSignatures = [
    ...selectedSignatures,
    ...(executiveTarget && !selectedSignatures.includes(executiveTarget.model.model_signature)
      ? [executiveTarget.model.model_signature]
      : []),
  ];

  const occupied: Array<{ x: number; y: number; width: number; height: number }> = [];
  const labelPlacements = new Map<
    string,
    { x: number; y: number; width: number; height: number; anchorX: number; anchorY: number }
  >();

  const overlaps = (
    a: { x: number; y: number; width: number; height: number },
    b: { x: number; y: number; width: number; height: number },
  ) =>
    a.x < b.x + b.width + 5 &&
    a.x + a.width + 5 > b.x &&
    a.y < b.y + b.height + 5 &&
    a.y + a.height + 5 > b.y;

  for (const signature of persistentSignatures) {
    const point = plotted.find((candidate) => candidate.model.model_signature === signature);
    if (!point) continue;
    const width = Math.min(220, Math.max(112, point.model.model_key.length * 7.2 + 28));
    const height = 38;
    const candidates = [
      { x: point.cx + 13, y: point.cy - 28 },
      { x: point.cx + 13, y: point.cy + 8 },
      { x: point.cx - width - 13, y: point.cy - 28 },
      { x: point.cx - width - 13, y: point.cy + 8 },
      { x: point.cx + 13, y: point.cy - 52 },
      { x: point.cx - width - 13, y: point.cy - 52 },
    ];
    const chosen =
      candidates
        .map((candidate) => ({
          x: Math.max(80, Math.min(838 - width, candidate.x)),
          y: Math.max(38, Math.min(280 - height, candidate.y)),
          width,
          height,
        }))
        .find((candidate) => !occupied.some((placed) => overlaps(candidate, placed))) ??
      {
        x: Math.max(80, Math.min(838 - width, point.cx + 13)),
        y: Math.max(38, Math.min(280 - height, point.cy - 28)),
        width,
        height,
      };
    occupied.push(chosen);
    labelPlacements.set(signature, {
      ...chosen,
      anchorX: chosen.x > point.cx ? chosen.x : chosen.x + width,
      anchorY: chosen.y + height / 2,
    });
  }

  return (
    <div className="executive-plot-shell interactive">
      <div className="executive-plot-hint"><i /> Blue = Pareto · click to focus · ⌘/Ctrl-click to keep multiple</div>
      <svg className="executive-plot" viewBox="0 0 900 340" role="img" aria-label={`Quality versus ${xLabel}`}>
        <g className="executive-plot-grid">
          {[0, 1, 2, 3, 4].map((step) => {
            const yy = 56 + step * 55;
            return <line key={step} x1="76" y1={yy} x2="840" y2={yy} />;
          })}
        </g>
        <line x1="76" y1="286" x2="840" y2="286" className="executive-axis" />
        <line x1="76" y1="44" x2="76" y2="286" className="executive-axis" />

        {persistentSignatures.map((signature) => {
          const point = plotted.find((candidate) => candidate.model.model_signature === signature);
          const placement = labelPlacements.get(signature);
          if (!point || !placement) return null;
          return (
            <g className="executive-point-label-group" key={`label-${signature}`}>
              <line
                x1={point.cx}
                y1={point.cy}
                x2={placement.anchorX}
                y2={placement.anchorY}
                className="executive-point-leader"
              />
              <rect
                x={placement.x}
                y={placement.y}
                width={placement.width}
                height={placement.height}
                rx="7"
                className="executive-point-label-bg"
              />
              <text x={placement.x + 9} y={placement.y + 14} className="executive-point-label-title">
                {point.model.model_key}
              </text>
              <text x={placement.x + 9} y={placement.y + 27} className="executive-point-label-meta">
                {formatX(point.xv)} · quality {scoreValue(point.yv)}
              </text>
            </g>
          );
        })}

        {plotted.map(({ model, cx, cy, onPareto }) => {
          const selected = selectedSignatures.includes(model.model_signature);
          const hoveredPoint = model.model_signature === hoveredSignature;
          return (
            <g
              className={[
                'executive-point',
                onPareto ? 'pareto' : '',
                selected ? 'selected' : '',
                hoveredPoint ? 'hovered' : '',
              ].filter(Boolean).join(' ')}
              key={model.model_signature}
              tabIndex={0}
              role="button"
              aria-label={`${model.model_key}: quality ${scoreValue(model.overall_quality_score)}, ${xLabel} ${formatX(x(model))}`}
              onMouseEnter={() => setHoveredSignature(model.model_signature)}
              onMouseLeave={() => setHoveredSignature(null)}
              onFocus={() => setHoveredSignature(model.model_signature)}
              onBlur={() => setHoveredSignature(null)}
              onClick={(event) => {
                const signature = model.model_signature;
                const multiSelect = event.metaKey || event.ctrlKey;
                setSelectedSignatures((current) => {
                  if (multiSelect) {
                    return current.includes(signature)
                      ? current.filter((item) => item !== signature)
                      : [...current, signature];
                  }
                  return current.length === 1 && current[0] === signature ? [] : [signature];
                });
              }}
            >
              {selected ? <circle cx={cx} cy={cy} r="11" className="executive-point-selection-ring" /> : null}
              <circle cx={cx} cy={cy} r={onPareto ? 8 : 6} />
            </g>
          );
        })}
        <text x="460" y="328" textAnchor="middle" className="executive-axis-title">{xLabel} · lower is better</text>
        <text x="20" y="165" textAnchor="middle" transform="rotate(-90 20 165)" className="executive-axis-title">
          Quality · higher is better
        </text>
      </svg>

      {hovered ? (
        <div
          className={[
            'executive-point-tooltip',
            hovered.cx > 690 ? 'align-right' : '',
            hovered.cy < 90 ? 'below' : '',
          ].filter(Boolean).join(' ')}
          style={{
            left: `${(hovered.cx / 900) * 100}%`,
            top: `${(hovered.cy / 340) * 100}%`,
          }}
        >
          <div className="executive-point-tooltip-title">
            <strong>{hovered.model.model_key}</strong>
            <RuntimeBadge model={hovered.model} compact />
          </div>
          <div className="executive-point-tooltip-metrics">
            <span><small>Quality</small><strong>{scoreValue(hovered.yv)}</strong></span>
            <span><small>{xLabel}</small><strong>{formatX(hovered.xv)}</strong></span>
          </div>
          <small>{hovered.onPareto ? 'Pareto-efficient' : 'Measured configuration'} · click to focus · ⌘/Ctrl-click to keep</small>
        </div>
      ) : null}
    </div>
  );
}

function CapabilityLeadership({
  capabilities,
  models,
}: {
  capabilities: DecisionCapabilitySummary[];
  models: DecisionModelSummary[];
}) {
  const modelBySignature = new Map(models.map((model) => [model.model_signature, model]));
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
              {winner ? (
                <span className="executive-model-meta">
                  <RuntimeBadge model={modelBySignature.get(winner.model_signature) ?? {
                    deployment: 'api',
                    runtime_key: '',
                    provider_key: '',
                    tags: [],
                  }} compact />
                </span>
              ) : null}
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


type DatasetFitMode = 'models' | 'families';

interface DatasetMatrixCell {
  dataset: string;
  key: string;
  label: string;
  score: number;
  observedCases: number;
  model?: DecisionModelSummary | null;
}

interface DatasetMatrixColumn {
  key: string;
  label: string;
  family?: string | null;
  model?: DecisionModelSummary | null;
}

function datasetLabel(value: string): string {
  const compact = value
    .replace(/-controlled-v\d+$/i, '')
    .replace(/-controlled$/i, '');
  const tokens = compact.replaceAll('_', '-').split('-').filter(Boolean);
  return tokens
    .map((token) => {
      const lower = token.toLowerCase();
      if (lower === 'oos') return 'OOS';
      if (lower === 'qa') return 'QA';
      if (lower === 'clinc150') return 'CLINC150';
      if (lower === 'banking77') return 'Banking77';
      return token.charAt(0).toUpperCase() + token.slice(1);
    })
    .join(' ');
}

function aggregateDatasetCells(
  rows: DecisionDatasetSummary[],
  models: DecisionModelSummary[],
  mode: DatasetFitMode,
): {
  cells: DatasetMatrixCell[];
  columns: DatasetMatrixColumn[];
  datasets: string[];
} {
  const modelBySignature = new Map(models.map((model) => [model.model_signature, model]));
  const modelByKey = new Map(models.map((model) => [model.model_key, model]));
  const grouped = new Map<string, { weighted: number; weight: number; dataset: string; key: string; label: string }>();

  for (const row of rows) {
    if (row.normalized_quality_score == null || !Number.isFinite(row.normalized_quality_score)) continue;
    const model = modelBySignature.get(row.model_signature) ?? modelByKey.get(row.model_key);
    const family = model?.family ?? 'Unclassified';
    const key = mode === 'models' ? row.model_signature : family;
    const label = mode === 'models' ? row.model_key : family;
    const weight = Math.max(1, row.observed_case_count || row.sample_count || 1);
    const groupKey = `${row.dataset_id}::${key}`;
    const current = grouped.get(groupKey) ?? {
      weighted: 0,
      weight: 0,
      dataset: row.dataset_id,
      key,
      label,
    };
    current.weighted += Number(row.normalized_quality_score) * weight;
    current.weight += weight;
    grouped.set(groupKey, current);
  }

  const cells = [...grouped.values()].map((item) => ({
    dataset: item.dataset,
    key: item.key,
    label: item.label,
    score: item.weighted / item.weight,
    observedCases: item.weight,
    model: mode === 'models' ? (modelBySignature.get(item.key) ?? null) : null,
  }));
  const datasets = [...new Set(cells.map((cell) => cell.dataset))].sort();
  const columns = [...new Map(
    cells.map((cell) => [
      cell.key,
      {
        key: cell.key,
        label: cell.label,
        family:
          mode === 'models'
            ? (modelBySignature.get(cell.key)?.family ?? null)
            : cell.label,
        model: mode === 'models' ? (modelBySignature.get(cell.key) ?? null) : null,
      },
    ]),
  ).values()].sort((a, b) => a.label.localeCompare(b.label));

  return { cells, columns, datasets };
}

function DatasetHeatmap({
  cells,
  columns,
  datasets,
}: {
  cells: DatasetMatrixCell[];
  columns: DatasetMatrixColumn[];
  datasets: string[];
}) {
  if (!cells.length || !columns.length || !datasets.length) {
    return <ExecutiveEmpty message="Project dataset-level CURRENT evidence to populate model × dataset fit." />;
  }

  const byKey = new Map(cells.map((cell) => [`${cell.dataset}::${cell.key}`, cell]));
  const winnerByDataset = new Map<string, string>();
  for (const dataset of datasets) {
    const candidates = cells
      .filter((cell) => cell.dataset === dataset)
      .sort((a, b) => b.score - a.score);
    if (candidates[0]) winnerByDataset.set(dataset, candidates[0].key);
  }

  return (
    <div className="dataset-heatmap-wrap">
      <div
        className="dataset-heatmap"
        style={{ gridTemplateColumns: `minmax(150px, 1.35fr) repeat(${columns.length}, minmax(70px, 1fr))` }}
      >
        <div className="dataset-heatmap-corner">Dataset</div>
        {columns.map((column) => (
          <div className="dataset-heatmap-column" key={column.key}>
            <strong>{column.label}</strong>
            <span className="dataset-column-meta">
              {column.family && column.family !== column.label ? <span>{column.family}</span> : null}
              {column.model ? <RuntimeBadge model={column.model} compact /> : null}
            </span>
          </div>
        ))}
        {datasets.flatMap((dataset) => {
          const datasetCells = columns.map((column) => {
            const cell = byKey.get(`${dataset}::${column.key}`);
            const score = cell?.score ?? null;
            const winner = winnerByDataset.get(dataset) === column.key;
            const normalized = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
            return (
              <div
                key={`${dataset}::${column.key}`}
                className={[
                  'dataset-heatmap-cell',
                  winner ? 'winner' : '',
                  score == null ? 'missing' : '',
                ].filter(Boolean).join(' ')}
                style={
                  score == null
                    ? undefined
                    : {
                        background: `linear-gradient(145deg, rgba(70, 108, 239, ${0.07 + normalized * 0.76}), rgba(70, 171, 204, ${0.04 + normalized * 0.30}))`,
                        color: normalized > 0.62 ? '#fff' : '#213149',
                      }
                }
                title={score == null ? 'No evidence' : `${column.label} · ${dataset}: ${score.toFixed(1)}`}
              >
                {score == null ? '—' : score.toFixed(1)}
              </div>
            );
          });
          return [
            <div className="dataset-heatmap-rowlabel" key={`${dataset}::label`}>
              <strong>{datasetLabel(dataset)}</strong>
              <span title={dataset}>{dataset}</span>
            </div>,
            ...datasetCells,
          ];
        })}
      </div>
    </div>
  );
}

function FamilyDatasetBars({
  cells,
  columns,
  datasets,
}: {
  cells: DatasetMatrixCell[];
  columns: DatasetMatrixColumn[];
  datasets: string[];
}) {
  if (!cells.length || !columns.length || !datasets.length) {
    return <ExecutiveEmpty message="At least one model family with dataset-level evidence is required." />;
  }

  const byKey = new Map(cells.map((cell) => [`${cell.dataset}::${cell.key}`, cell]));
  const palette = ['#4f67ee', '#31a775', '#835fe6', '#e29a43', '#4b9eb7', '#7b879a'];
  const width = Math.max(900, datasets.length * Math.max(118, columns.length * 35));
  const left = 62;
  const right = 30;
  const top = 34;
  const bottom = 74;
  const chartW = width - left - right;
  const chartH = 280;
  const groupW = chartW / Math.max(1, datasets.length);
  const innerW = Math.min(groupW * 0.75, columns.length * 26);
  const barW = Math.max(7, Math.min(22, innerW / Math.max(1, columns.length) - 3));

  return (
    <div className="family-bars-wrap">
      <div className="family-bars-legend">
        {columns.map((column, index) => (
          <span key={column.key}><i style={{ background: palette[index % palette.length] }} />{column.label}</span>
        ))}
      </div>
      <svg
        className="family-dataset-bars"
        viewBox={`0 0 ${width} ${top + chartH + bottom}`}
        style={{ minWidth: width }}
        role="img"
        aria-label="Model family performance by dataset"
      >
        {[0, 25, 50, 75, 100].map((tick) => {
          const y = top + chartH - (tick / 100) * chartH;
          return (
            <g key={tick}>
              <line x1={left} y1={y} x2={width - right} y2={y} className="family-bars-grid" />
              <text x={left - 10} y={y + 3} textAnchor="end" className="family-bars-tick">{tick}</text>
            </g>
          );
        })}
        {datasets.map((dataset, datasetIndex) => {
          const groupX = left + datasetIndex * groupW;
          const startX = groupX + (groupW - columns.length * (barW + 3)) / 2;
          return (
            <g key={dataset}>
              {columns.map((column, columnIndex) => {
                const score = byKey.get(`${dataset}::${column.key}`)?.score ?? 0;
                const barHeight = (Math.max(0, Math.min(100, score)) / 100) * chartH;
                return (
                  <rect
                    key={column.key}
                    x={startX + columnIndex * (barW + 3)}
                    y={top + chartH - barHeight}
                    width={barW}
                    height={barHeight}
                    rx="3"
                    fill={palette[columnIndex % palette.length]}
                  >
                    <title>{`${column.label} · ${dataset}: ${score.toFixed(1)}`}</title>
                  </rect>
                );
              })}
              <text
                x={groupX + groupW / 2}
                y={top + chartH + 24}
                textAnchor="middle"
                className="family-bars-label"
              >
                {datasetLabel(dataset)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function DatasetWinners({
  cells,
  datasets,
}: {
  cells: DatasetMatrixCell[];
  datasets: string[];
}) {
  const winners = datasets
    .map((dataset) => {
      const ranked = cells
        .filter((cell) => cell.dataset === dataset)
        .sort((a, b) => b.score - a.score);
      return { dataset, winner: ranked[0], runnerUp: ranked[1] };
    })
    .filter((item) => item.winner);

  return (
    <div className="dataset-winners">
      {winners.map(({ dataset, winner, runnerUp }) => (
        <div className="dataset-winner-row" key={dataset}>
          <div>
            <strong>{datasetLabel(dataset)}</strong>
            <span>{dataset}</span>
          </div>
          <div>
            <strong>{winner.label}</strong>
            <span className="dataset-winner-meta">
              <span>{runnerUp ? `+${(winner.score - runnerUp.score).toFixed(1)} vs #2` : 'only measured option'}</span>
              {winner.model ? <RuntimeBadge model={winner.model} compact /> : null}
            </span>
          </div>
          <strong>{winner.score.toFixed(1)}</strong>
        </div>
      ))}
    </div>
  );
}

function DatasetFitExecutivePage({
  models,
  datasets: datasetRows,
}: {
  models: DecisionModelSummary[];
  datasets: DecisionDatasetSummary[];
}) {
  const [mode, setMode] = useState<DatasetFitMode>('models');
  const capabilities = useMemo(
    () => [...new Set(datasetRows.map((row) => row.capability_id))].sort(),
    [datasetRows],
  );
  const families = useMemo(
    () => [...new Set(models.map((model) => model.family).filter((value): value is string => Boolean(value)))].sort(),
    [models],
  );
  const [capability, setCapability] = useState('all');
  const [family, setFamily] = useState('all');

  const filteredRows = useMemo(() => {
    const allowedModels =
      family === 'all'
        ? null
        : new Set(
            models
              .filter((model) => model.family === family)
              .map((model) => model.model_signature),
          );
    return datasetRows.filter(
      (row) =>
        (capability === 'all' || row.capability_id === capability) &&
        (allowedModels == null || allowedModels.has(row.model_signature)),
    );
  }, [datasetRows, capability, family, models]);

  const matrix = useMemo(
    () => aggregateDatasetCells(filteredRows, models, mode),
    [filteredRows, models, mode],
  );

  const winCounts = new Map<string, number>();
  for (const dataset of matrix.datasets) {
    const winner = matrix.cells
      .filter((cell) => cell.dataset === dataset)
      .sort((a, b) => b.score - a.score)[0];
    if (winner) winCounts.set(winner.label, (winCounts.get(winner.label) ?? 0) + 1);
  }
  const topWinner = [...winCounts.entries()].sort((a, b) => b[1] - a[1])[0];

  const spreads = matrix.datasets
    .map((dataset) => {
      const scores = matrix.cells
        .filter((cell) => cell.dataset === dataset)
        .map((cell) => cell.score)
        .sort((a, b) => b - a);
      return scores.length >= 2
        ? { dataset, gap: scores[0] - scores[1], range: scores[0] - scores[scores.length - 1] }
        : null;
    })
    .filter((value): value is { dataset: string; gap: number; range: number } => value != null);
  const strongestSeparation = [...spreads].sort((a, b) => b.gap - a.gap)[0];
  const tightest = [...spreads].sort((a, b) => a.range - b.range)[0];

  const statement = topWinner
    ? mode === 'models'
      ? `${topWinner[0]} wins the most measured datasets in the current cohort.`
      : `${topWinner[0]} is the strongest family across the broadest set of measured datasets.`
    : 'Dataset-level evidence is not sufficient to establish a model–dataset fit.';

  const evidence = topWinner
    ? `${topWinner[1]} win${topWinner[1] === 1 ? '' : 's'} across ${matrix.datasets.length} comparable datasets${capability === 'all' ? '' : ` within ${capability}`}.`
    : 'Project CURRENT dataset summaries to identify where individual models and model families are strongest.';

  return (
    <ExecutiveFrame
      active="dataset-fit"
      eyebrow="Executive · Model × Dataset fit"
      title="Which model fits which dataset best?"
      statement={statement}
      evidence={evidence}
    >
      <section className="dataset-fit-controls">
        <div className="dataset-fit-toggle" role="group" aria-label="Dataset fit aggregation">
          <button type="button" className={mode === 'models' ? 'active' : ''} onClick={() => setMode('models')}>
            All models
          </button>
          <button
            type="button"
            className={mode === 'families' ? 'active' : ''}
            onClick={() => {
              setMode('families');
              setFamily('all');
            }}
          >
            By family
          </button>
        </div>
        <label>
          <span>Capability</span>
          <select value={capability} onChange={(event) => setCapability(event.target.value)}>
            <option value="all">All capabilities</option>
            {capabilities.map((value) => <option key={value} value={value}>{datasetLabel(value)}</option>)}
          </select>
        </label>
        <label>
          <span>Model family</span>
          <select value={family} onChange={(event) => setFamily(event.target.value)} disabled={mode === 'families'}>
            <option value="all">All families</option>
            {families.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </section>

      <div className="dataset-fit-grid">
        <section className="executive-visual-card dataset-fit-main">
          <div className="executive-visual-heading">
            <div>
              <span>{mode === 'models' ? 'Model × Dataset performance' : 'Family performance by dataset'}</span>
              <h3>
                {mode === 'models'
                  ? 'Highlighted cells show the best measured model for each dataset'
                  : 'Average CURRENT quality by model family'}
              </h3>
            </div>
            <Database size={20} />
          </div>
          {mode === 'models' ? (
            <DatasetHeatmap cells={matrix.cells} columns={matrix.columns} datasets={matrix.datasets} />
          ) : (
            <FamilyDatasetBars cells={matrix.cells} columns={matrix.columns} datasets={matrix.datasets} />
          )}
        </section>

        <aside className="dataset-fit-aside">
          <section className="dataset-fit-side-card">
            <div className="dataset-fit-side-heading">
              <span>Dataset winners</span>
              <strong>{mode === 'models' ? 'Best model' : 'Best family'}</strong>
            </div>
            <DatasetWinners cells={matrix.cells} datasets={matrix.datasets} />
          </section>

          <section className="dataset-fit-side-card dataset-fit-takeaways">
            <div className="dataset-fit-side-heading">
              <span>Key takeaways</span>
              <strong>Current evidence</strong>
            </div>
            <div className="dataset-fit-takeaway">
              <i>1</i>
              <div>
                <strong>{topWinner ? `${topWinner[0]} wins most often` : 'No dominant winner yet'}</strong>
                <span>{topWinner ? `${topWinner[1]} of ${matrix.datasets.length} measured datasets.` : 'More comparable datasets are needed.'}</span>
              </div>
            </div>
            <div className="dataset-fit-takeaway">
              <i>2</i>
              <div>
                <strong>{strongestSeparation ? `${datasetLabel(strongestSeparation.dataset)} separates competitors most` : 'No clear separation signal'}</strong>
                <span>{strongestSeparation ? `${strongestSeparation.gap.toFixed(1)} point lead over #2.` : 'At least two competitors per dataset are required.'}</span>
              </div>
            </div>
            <div className="dataset-fit-takeaway">
              <i>3</i>
              <div>
                <strong>{tightest ? `${datasetLabel(tightest.dataset)} is the tightest contest` : 'No clustering signal yet'}</strong>
                <span>{tightest ? `${tightest.range.toFixed(1)} point spread from best to worst measured option.` : 'More overlapping evidence is required.'}</span>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </ExecutiveFrame>
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
  const bestRate = Math.min(...rows.map((model) => Number(model.failure_rate)));
  return (
    <div className="executive-reliability">
      {rows.map((model) => {
        const raw = Number(model.failure_rate);
        const width = Math.max(1.5, (raw / max) * 100);
        const tiedBest = Math.abs(raw - bestRate) < 1e-12;
        return (
          <div className={tiedBest ? 'executive-reliability-row best' : 'executive-reliability-row'} key={model.model_signature}>
            <div>
              <strong>{model.model_key}</strong>
              <span className="executive-model-meta">
                <span>{model.quality_coverage_complete ? 'Complete quality coverage' : 'Partial quality coverage'}</span>
                <RuntimeBadge model={model} compact />
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
  const datasets = decision?.dataset_summaries ?? [];
  const [qualityDataset, setQualityDataset] = useState('overall');

  const qualityDatasetIds = useMemo(
    () => [...new Set(datasets.map((row) => row.dataset_id))].sort(),
    [datasets],
  );
  const qualityRanking = useMemo(
    () =>
      qualityDataset === 'overall'
        ? overallQualityRanking(models)
        : datasetQualityRanking(datasets, models, qualityDataset),
    [qualityDataset, datasets, models],
  );
  const qualityLeader = qualityRanking[0]?.model;
  const qualityLeaderScore = qualityRanking[0]?.score ?? null;

  const speedModels = models.filter((model) => model.latency_p50_ms != null && model.overall_quality_score != null);
  const speedPareto = speedModels.filter((model) => model.observed_quality_latency_pareto);
  const speedChoice =
    [...speedPareto].sort((a, b) => modelQuality(b) - modelQuality(a))[0] ??
    [...speedModels].sort((a, b) => Number(a.latency_p50_ms) - Number(b.latency_p50_ms))[0];

  const sizeModels = models.filter(
    (model) =>
      model.artifact_size_bytes != null &&
      Number.isFinite(model.artifact_size_bytes) &&
      model.overall_quality_score != null,
  );
  const sizePareto = sizeModels.filter(
    (model) => model.observed_quality_artifact_size_pareto,
  );
  const sizeChoice = [...sizePareto].sort((a, b) => modelQuality(b) - modelQuality(a))[0];
  const smallestPareto = [...sizePareto].sort(
    (a, b) => Number(a.artifact_size_bytes) - Number(b.artifact_size_bytes),
  )[0];

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
  const reliabilityBestRate = reliabilityLeader?.failure_rate ?? null;
  const reliabilityTies =
    reliabilityBestRate == null
      ? []
      : reliableModels.filter(
          (model) => Math.abs(Number(model.failure_rate) - Number(reliabilityBestRate)) < 1e-12,
        );

  if (view === 'quality') {
    const runnerUp = qualityRanking[1];
    const margin =
      qualityLeaderScore != null && runnerUp
        ? qualityLeaderScore - runnerUp.score
        : null;
    const selectedDatasetLabel =
      qualityDataset === 'overall' ? 'overall benchmark quality' : datasetLabel(qualityDataset);
    return (
      <ExecutiveFrame
        active="quality"
        eyebrow="Executive · Quality"
        title={qualityDataset === 'overall' ? 'Who is strongest overall?' : `Who is strongest on ${datasetLabel(qualityDataset)}?`}
        statement={
          qualityLeader
            ? `${qualityLeader.model_key} leads the CURRENT cohort on ${selectedDatasetLabel}.`
            : 'No quality leader can be established yet.'
        }
        evidence={
          qualityLeaderScore != null
            ? `Score ${scoreValue(qualityLeaderScore)}${margin == null ? '' : ` · ${margin.toFixed(1)} points ahead of #2`}.`
            : 'Project completed comparable results to establish a quality leader.'
        }
      >
        <section className="executive-visual-card executive-quality-card">
          <div className="executive-visual-heading executive-quality-heading">
            <div>
              <span>{qualityDataset === 'overall' ? 'Overall quality ranking' : 'Dataset quality ranking'}</span>
              <h3>{qualityDataset === 'overall' ? 'Comparable coverage · higher is better' : `${datasetLabel(qualityDataset)} · higher is better`}</h3>
            </div>
            <div className="executive-quality-actions">
              <label>
                <span>Dataset</span>
                <select value={qualityDataset} onChange={(event) => setQualityDataset(event.target.value)}>
                  <option value="overall">Overall</option>
                  {qualityDatasetIds.map((datasetId) => (
                    <option key={datasetId} value={datasetId}>{datasetLabel(datasetId)}</option>
                  ))}
                </select>
              </label>
              <Trophy size={20} />
            </div>
          </div>
          <QualityBars items={qualityRanking} />
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

  if (view === 'size') {
    return (
      <ExecutiveFrame
        active="size"
        eyebrow="Executive · Model size"
        title="How much model do we need for the quality we get?"
        statement={
          sizeChoice
            ? `${sizePareto.length} model${sizePareto.length === 1 ? '' : 's'} define the current quality–size Pareto frontier; ${sizeChoice.model_key} reaches its highest measured quality.`
            : 'There is not enough measured model-size evidence to establish a Pareto frontier.'
        }
        evidence={
          sizeChoice && smallestPareto
            ? `Highest-quality Pareto point: ${scoreValue(sizeChoice.overall_quality_score)} at ${modelSizeValue(sizeChoice.artifact_size_bytes)} · smallest Pareto point: ${smallestPareto.model_key} at ${modelSizeValue(smallestPareto.artifact_size_bytes)}.`
            : 'A real artifact size and comparable overall quality are required for each plotted model.'
        }
      >
        <section className="executive-visual-card">
          <div className="executive-visual-heading">
            <div>
              <span>Quality × model artifact size</span>
              <h3>Upper-left is efficient: more quality, fewer GB</h3>
            </div>
            <HardDrive size={20} />
          </div>
          <TradeoffPlot
            models={sizeModels}
            x={(model) => model.artifact_size_bytes ?? null}
            xLabel="Model size"
            formatX={modelSizeValue}
            pareto={(model) => model.observed_quality_artifact_size_pareto}
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
          costModels.length === 1 && costChoice
            ? `${costChoice.model_key} is the only API model with comparable priced evidence today.`
            : costChoice
              ? `${costChoice.model_key} offers the strongest measured quality–cost position among priced API models.`
              : 'There is not enough priced API evidence to establish a cost trade-off.'
        }
        evidence={
          costModels.length === 1 && costChoice
            ? `${scoreValue(costChoice.overall_quality_score)} quality at ${costValue(costChoice.provider_cost_per_1k_cases_usd)} per 1k cases · at least one more priced model is needed for a frontier claim.`
            : costChoice
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

  if (view === 'dataset-fit') {
    return <DatasetFitExecutivePage models={models} datasets={datasets} />;
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
          <CapabilityLeadership capabilities={capabilities} models={models} />
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
        reliabilityTies.length > 1 && reliabilityLeader
          ? `${reliabilityTies.length} models are tied at the lowest observed failure rate.`
          : reliabilityLeader
            ? `${reliabilityLeader.model_key} has the lowest observed failure rate in the CURRENT cohort.`
            : 'Reliability cannot be ranked with the current evidence.'
      }
      evidence={
        reliabilityTies.length > 1 && reliabilityLeader
          ? `All tied models are at ${failureValue(reliabilityLeader.failure_rate)} observed failures; more failure evidence is needed to differentiate operational reliability.`
          : reliabilityLeader
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
