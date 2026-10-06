import { useMemo, useState } from 'react';
import {
  Boxes,
  Download,
  Info,
  Search,
  Sparkles,
  Star,
  TrendingUp,
} from 'lucide-react';
import { overview } from '../data';
import type {
  FrontierPoint,
  SensitivityPoint,
} from '../types';
import { bytes, milliseconds, points, score } from '../utils';
import { PageHeader } from '../components/Shell';

type FrontierMetric =
  | 'parameters_b'
  | 'artifact_size_bytes'
  | 'peak_rss_bytes'
  | 'latency_p50_ms';
type FrontierMode = 'family' | 'compression';
type FrontierSort = 'parameters' | 'quality' | 'metric' | 'model';

const FRONTIER_METRICS: Record<
  FrontierMetric,
  {
    label: string;
    compactLabel: string;
    format: (value: number | null) => string;
  }
> = {
  parameters_b: {
    label: 'Parameters',
    compactLabel: 'Params',
    format: (value) => value == null ? '—' : `${value}B`,
  },
  artifact_size_bytes: {
    label: 'Artifact size',
    compactLabel: 'Artifact',
    format: bytes,
  },
  peak_rss_bytes: {
    label: 'Peak RAM',
    compactLabel: 'Peak RAM',
    format: bytes,
  },
  latency_p50_ms: {
    label: 'P50 latency',
    compactLabel: 'Latency',
    format: milliseconds,
  },
};

function paretoFor(point: FrontierPoint, metric: FrontierMetric): boolean {
  if (metric === 'parameters_b') return point.pareto_parameters;
  if (metric === 'artifact_size_bytes') return point.pareto_artifact_size;
  if (metric === 'peak_rss_bytes') return point.pareto_peak_rss;
  return point.pareto_latency;
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function scale(
  value: number,
  min: number,
  max: number,
  targetMin: number,
  targetMax: number,
): number {
  if (max === min) return (targetMin + targetMax) / 2;
  return targetMin + ((value - min) / (max - min)) * (targetMax - targetMin);
}

function qualityText(value: number | null): string {
  if (value == null) return '—';
  return value <= 1 ? value.toFixed(2) : score(value);
}

function frontierMetricValue(point: FrontierPoint, metric: FrontierMetric): number | null {
  const value = point[metric];
  return finite(value) ? value : null;
}

function FrontierChart({
  points: data,
  metric,
  mode,
  highlightedSignature,
  selectedSignature,
  onHover,
  onSelect,
}: {
  points: FrontierPoint[];
  metric: FrontierMetric;
  mode: FrontierMode;
  highlightedSignature: string | null;
  selectedSignature: string | null;
  onHover: (signature: string | null) => void;
  onSelect: (signature: string) => void;
}) {
  const pointsWithData = data.filter(
    (point) => finite(point[metric]) && finite(point.quality),
  );
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    point: FrontierPoint;
  } | null>(null);

  if (pointsWithData.length === 0) {
    return (
      <div className="frontier-empty-state">
        <div className="frontier-empty-icon"><TrendingUp size={18} /></div>
        <strong>No comparable frontier evidence yet</strong>
        <span>Run and project local standard benchmarks to populate this view.</span>
      </div>
    );
  }

  const rawXs = pointsWithData.map((point) => Number(point[metric]));
  const transformX = (value: number) =>
    metric === 'parameters_b' && value > 0 ? Math.log10(value) : value;
  const transformedXs = rawXs.map(transformX);
  const minX = Math.min(...transformedXs);
  const maxX = Math.max(...transformedXs);
  const xPad = maxX === minX ? 1 : (maxX - minX) * 0.08;
  const domainMinX = minX - xPad;
  const domainMaxX = maxX + xPad;

  const qualities = pointsWithData.map((point) => Number(point.quality));
  const observedMinY = Math.min(...qualities);
  const observedMaxY = Math.max(...qualities);
  const normalizedQuality = observedMinY >= 0 && observedMaxY <= 1;
  const yPad = normalizedQuality
    ? 0
    : Math.max(0.02, (observedMaxY - observedMinY) * 0.12);
  const minY = normalizedQuality ? 0 : observedMinY - yPad;
  const maxY = normalizedQuality ? 1 : observedMaxY + yPad;

  const x = (point: FrontierPoint) =>
    scale(transformX(Number(point[metric])), domainMinX, domainMaxX, 78, 844);
  const y = (point: FrontierPoint) =>
    scale(Number(point.quality), minY, maxY, 286, 36);

  const groups = new Map<string, FrontierPoint[]>();
  for (const point of pointsWithData.filter((item) => paretoFor(item, metric))) {
    const key = mode === 'family' ? point.family : point.compression_group;
    if (!key) continue;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  }

  const yTicks = normalizedQuality
    ? [0, 0.25, 0.5, 0.75, 1]
    : Array.from({ length: 5 }, (_, index) => minY + ((maxY - minY) * index) / 4);

  const uniqueMetricValues = [...new Set(rawXs)].sort((a, b) => a - b);
  const xTicks =
    uniqueMetricValues.length <= 5
      ? uniqueMetricValues
      : Array.from({ length: 5 }, (_, index) => {
          const transformed = domainMinX + ((domainMaxX - domainMinX) * index) / 4;
          return metric === 'parameters_b' ? Math.pow(10, transformed) : transformed;
        });

  const sortedForLabels = [...pointsWithData].sort((a, b) => {
    const xDelta = Number(a[metric]) - Number(b[metric]);
    if (xDelta !== 0) return xDelta;
    return Number(b.quality) - Number(a.quality);
  });

  return (
    <div className="frontier-chart-shell">
      <svg
        className="frontier-scatter"
        viewBox="0 0 900 340"
        role="img"
        aria-label="Quality versus deployment resource Pareto frontier"
        onMouseLeave={() => {
          setTooltip(null);
          onHover(null);
        }}
      >
        <g className="frontier-grid">
          {yTicks.map((tick) => {
            const yy = scale(tick, minY, maxY, 286, 36);
            return (
              <g key={`y-${tick}`}>
                <line x1="78" y1={yy} x2="844" y2={yy} />
                <text x="66" y={yy + 3} textAnchor="end">
                  {normalizedQuality ? tick.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') : score(tick)}
                </text>
              </g>
            );
          })}
          {xTicks.map((tick) => {
            const xx = scale(transformX(tick), domainMinX, domainMaxX, 78, 844);
            return (
              <g key={`x-${tick}`}>
                <line x1={xx} y1="36" x2={xx} y2="286" />
                <text x={xx} y="306" textAnchor="middle">
                  {FRONTIER_METRICS[metric].format(tick)}
                </text>
              </g>
            );
          })}
        </g>

        <line x1="78" y1="286" x2="844" y2="286" className="frontier-axis" />
        <line x1="78" y1="36" x2="78" y2="286" className="frontier-axis" />

        {[...groups.entries()].map(([group, groupPoints], index) => {
          const ordered = [...groupPoints].sort(
            (a, b) => Number(a[metric]) - Number(b[metric]),
          );
          const coordinates = ordered
            .map((point) => `${x(point)},${y(point)}`)
            .join(' ');
          return (
            <polyline
              key={group}
              points={coordinates}
              className={`frontier-spine frontier-spine-${index % 6}`}
            />
          );
        })}

        {sortedForLabels.map((point, index) => {
          const pareto = paretoFor(point, metric);
          const isHighlighted = highlightedSignature === point.model_signature;
          const isSelected = selectedSignature === point.model_signature;
          const hasFocus = Boolean(highlightedSignature || selectedSignature);
          const cx = x(point);
          const cy = y(point);
          const toLeft = cx > 700;
          const sameXPosition = sortedForLabels
            .slice(0, index)
            .filter((other) => Number(other[metric]) === Number(point[metric])).length;
          const labelY =
            cy + (pareto ? -10 : 17) + sameXPosition * (pareto ? -12 : 12);

          return (
            <g
              key={point.model_signature}
              className={[
                'frontier-node',
                pareto ? 'pareto' : 'dominated',
                isHighlighted ? 'highlighted' : '',
                isSelected ? 'selected' : '',
                hasFocus && !isHighlighted && !isSelected ? 'deemphasized' : '',
              ].filter(Boolean).join(' ')}
              onMouseEnter={(event) => {
                const rect = event.currentTarget.closest('.frontier-chart-shell')?.getBoundingClientRect();
                if (rect) {
                  setTooltip({
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                    point,
                  });
                }
                onHover(point.model_signature);
              }}
              onMouseMove={(event) => {
                const rect = event.currentTarget.closest('.frontier-chart-shell')?.getBoundingClientRect();
                if (rect) {
                  setTooltip((current) => current ? {
                    ...current,
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                  } : null);
                }
              }}
              onMouseLeave={() => {
                setTooltip(null);
                onHover(null);
              }}
              onClick={() => onSelect(point.model_signature)}
            >
              <circle
                className="frontier-node-halo"
                cx={cx}
                cy={cy}
                r={isHighlighted || isSelected ? 12 : 0}
              />
              <circle
                className="frontier-node-dot"
                cx={cx}
                cy={cy}
                r={pareto ? 7 : 5.5}
              />
              <text
                x={toLeft ? cx - 10 : cx + 10}
                y={labelY}
                textAnchor={toLeft ? 'end' : 'start'}
                className="frontier-node-label"
              >
                {point.model_key}
              </text>
              <text
                x={toLeft ? cx - 10 : cx + 10}
                y={labelY + 12}
                textAnchor={toLeft ? 'end' : 'start'}
                className="frontier-node-meta"
              >
                {point.parameters_b == null ? '' : `${point.parameters_b}B`}
                {point.parameters_b != null && point.quantization ? ' · ' : ''}
                {point.quantization ?? ''}
              </text>
            </g>
          );
        })}

        <text x="462" y="332" textAnchor="middle" className="frontier-axis-title">
          {FRONTIER_METRICS[metric].label} · lower is better
        </text>
        <text
          x="19"
          y="165"
          textAnchor="middle"
          transform="rotate(-90 19 165)"
          className="frontier-axis-title"
        >
          Quality · higher is better
        </text>
      </svg>

      {tooltip ? (
        <div
          className="chart-dot-tooltip frontier-tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="dot-tooltip-header">
            <span
              className={`dot-tooltip-badge ${paretoFor(tooltip.point, metric) ? 'pareto' : 'dominated'}`}
            />
            <strong className="dot-tooltip-title">{tooltip.point.model_key}</strong>
          </div>
          <div className="dot-tooltip-body">
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">Quality</span>
              <span className="dot-tooltip-val highlight">{qualityText(tooltip.point.quality)}</span>
            </div>
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">{FRONTIER_METRICS[metric].label}</span>
              <span className="dot-tooltip-val">
                {FRONTIER_METRICS[metric].format(frontierMetricValue(tooltip.point, metric))}
              </span>
            </div>
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">Quantization</span>
              <span className="dot-tooltip-val">{tooltip.point.quantization ?? '—'}</span>
            </div>
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">State</span>
              <span className={`dot-tooltip-val ${paretoFor(tooltip.point, metric) ? 'is-pareto' : ''}`}>
                {paretoFor(tooltip.point, metric) ? 'Pareto-efficient' : 'Dominated'}
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function downloadFrontierCsv(points: FrontierPoint[], metric: FrontierMetric) {
  const escape = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const rows = [
    ['model', 'family', 'parameters_b', 'quantization', 'quality', metric, 'state'],
    ...points.map((point) => [
      point.model_key,
      point.family,
      point.parameters_b,
      point.quantization,
      point.quality,
      point[metric],
      paretoFor(point, metric) ? 'pareto' : 'dominated',
    ]),
  ];
  const csv = rows.map((row) => row.map(escape).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `mcb-frontier-${metric}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function FrontierPage() {
  const payload = overview.frontier;
  const [metric, setMetric] = useState<FrontierMetric>('parameters_b');
  const [mode, setMode] = useState<FrontierMode>('family');
  const [family, setFamily] = useState('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<FrontierSort>('parameters');
  const [hoveredSignature, setHoveredSignature] = useState<string | null>(null);
  const [selectedSignature, setSelectedSignature] = useState<string | null>(null);

  const localPoints = useMemo(
    () =>
      (payload?.points ?? []).filter(
        (point) =>
          point.deployment === 'local' &&
          (family === 'all' || point.family === family),
      ),
    [payload, family],
  );

  const comparablePoints = localPoints.filter(
    (point) => finite(point.quality) && finite(point[metric]),
  );
  const paretoPoints = comparablePoints.filter((point) => paretoFor(point, metric));
  const paretoCount = paretoPoints.length;
  const highlightedSignature = hoveredSignature ?? selectedSignature;

  const bestOverall = [...comparablePoints]
    .sort((a, b) => Number(b.quality) - Number(a.quality))[0];

  const efficientSmall = [...paretoPoints]
    .sort((a, b) => Number(a[metric]) - Number(b[metric]))[0];

  const orderedPareto = [...paretoPoints].sort(
    (a, b) => Number(a[metric]) - Number(b[metric]),
  );
  let largestGain:
    | { from: FrontierPoint; to: FrontierPoint; delta: number }
    | undefined;
  for (let index = 1; index < orderedPareto.length; index += 1) {
    const from = orderedPareto[index - 1];
    const to = orderedPareto[index];
    const delta = Number(to.quality) - Number(from.quality);
    if (delta > 0 && (!largestGain || delta > largestGain.delta)) {
      largestGain = { from, to, delta };
    }
  }

  const tablePoints = [...comparablePoints]
    .filter((point) => {
      const normalized = query.trim().toLowerCase();
      if (!normalized) return true;
      return [
        point.model_key,
        point.family,
        point.quantization,
        paretoFor(point, metric) ? 'pareto' : 'dominated',
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized));
    })
    .sort((a, b) => {
      if (sort === 'quality') return Number(b.quality) - Number(a.quality);
      if (sort === 'metric') return Number(a[metric]) - Number(b[metric]);
      if (sort === 'model') return a.model_key.localeCompare(b.model_key);
      return Number(a.parameters_b ?? Infinity) - Number(b.parameters_b ?? Infinity);
    });

  const selectedFamilyLabel =
    family === 'all' ? 'all local families' : family;

  return (
    <div className="frontier-page">
      <PageHeader
        eyebrow="Local deployment frontier"
        title="Pareto Frontier"
        description="Explore where model scale and compression buy real quality — and where extra parameters, memory or latency stop paying back."
        actions={
          <div className="frontier-header-kpis">
            <div className="frontier-header-kpi">
              <span className="frontier-header-kpi-icon"><Boxes size={16} /></span>
              <div><strong>{localPoints.length}</strong><small>Local configs</small></div>
              <Info size={13} />
            </div>
            <div className="frontier-header-kpi">
              <span className="frontier-header-kpi-icon"><Star size={16} /></span>
              <div><strong>{paretoCount}</strong><small>Pareto-efficient</small></div>
              <Info size={13} />
            </div>
          </div>
        }
      />

      <section className="frontier-filter-bar">
        <label>
          <span>X axis</span>
          <select
            value={metric}
            onChange={(event) => {
              setMetric(event.target.value as FrontierMetric);
              setSelectedSignature(null);
            }}
          >
            {Object.entries(FRONTIER_METRICS).map(([key, config]) => (
              <option key={key} value={key}>{config.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Connect</span>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as FrontierMode)}
          >
            <option value="family">Model family scaling</option>
            <option value="compression">Compression variants</option>
          </select>
        </label>
        <label>
          <span>Family</span>
          <select
            value={family}
            onChange={(event) => {
              setFamily(event.target.value);
              setSelectedSignature(null);
            }}
          >
            <option value="all">All families</option>
            {(payload?.families ?? []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
      </section>

      <div className="frontier-primary-grid">
        <section className="frontier-chart-card">
          <div className="frontier-card-heading">
            <div>
              <h2>Quality × {FRONTIER_METRICS[metric].label}</h2>
              <p>
                Solid points are Pareto-efficient. Dominated configurations stay visible
                as muted evidence for the selected cohort.
              </p>
            </div>
            <div className="frontier-legend">
              <span><i className="frontier-legend-dot pareto" /> Pareto-efficient</span>
              <span><i className="frontier-legend-dot dominated" /> Dominated</span>
            </div>
          </div>
          <FrontierChart
            points={localPoints}
            metric={metric}
            mode={mode}
            highlightedSignature={highlightedSignature}
            selectedSignature={selectedSignature}
            onHover={setHoveredSignature}
            onSelect={(signature) =>
              setSelectedSignature((current) => current === signature ? null : signature)
            }
          />
        </section>

        <aside className="frontier-insights-card">
          <div className="frontier-insights-title">
            <span><Sparkles size={16} /></span>
            <div>
              <strong>Key takeaways</strong>
              <small>Derived from the current filters</small>
            </div>
          </div>

          <div className="frontier-insight">
            <span className="frontier-insight-icon"><Star size={16} /></span>
            <div>
              <small>Best overall model</small>
              <strong>{bestOverall?.model_key ?? 'No measured model'}</strong>
              <p>
                {bestOverall
                  ? `Highest measured quality (${qualityText(bestOverall.quality)}) in ${selectedFamilyLabel}.`
                  : 'Project standard benchmark evidence to unlock this insight.'}
              </p>
            </div>
          </div>

          <div className="frontier-insight">
            <span className="frontier-insight-icon"><TrendingUp size={16} /></span>
            <div>
              <small>Largest quality gain</small>
              <strong>{largestGain ? `+${largestGain.delta.toFixed(2)}` : '—'}</strong>
              <p>
                {largestGain
                  ? `${largestGain.from.model_key} → ${largestGain.to.model_key}`
                  : 'At least two Pareto points are needed for a scaling delta.'}
              </p>
            </div>
          </div>

          <div className="frontier-insight">
            <span className="frontier-insight-icon"><Boxes size={16} /></span>
            <div>
              <small>
                {metric === 'parameters_b' ? 'Most efficient small model' : `Lowest ${FRONTIER_METRICS[metric].compactLabel.toLowerCase()}`}
              </small>
              <strong>{efficientSmall?.model_key ?? '—'}</strong>
              <p>
                {efficientSmall
                  ? `Pareto-efficient at ${FRONTIER_METRICS[metric].format(frontierMetricValue(efficientSmall, metric))}.`
                  : 'No Pareto point is available for this metric.'}
              </p>
            </div>
          </div>

          <div className="frontier-insight summary">
            <span className="frontier-insight-icon"><Info size={16} /></span>
            <div>
              <small>Frontier summary</small>
              <strong>
                {comparablePoints.length
                  ? `${paretoCount} of ${comparablePoints.length} measured configs`
                  : 'No comparable evidence'}
              </strong>
              <p>
                {comparablePoints.length
                  ? `${Math.round((paretoCount / comparablePoints.length) * 100)}% of this cohort is Pareto-efficient on ${FRONTIER_METRICS[metric].label.toLowerCase()}.`
                  : 'Run and project local benchmarks to populate the frontier.'}
              </p>
            </div>
          </div>
        </aside>
      </div>

      <section className="frontier-results-card">
        <div className="frontier-results-heading">
          <div>
            <h2>Model results</h2>
            <p>All measured local models in the selected cohort, with frontier state and deployment evidence.</p>
          </div>
          <div className="frontier-results-actions">
            <label className="frontier-search">
              <Search size={15} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search models..."
                aria-label="Search frontier models"
              />
            </label>
            <button
              type="button"
              className="frontier-download"
              onClick={() => downloadFrontierCsv(tablePoints, metric)}
              disabled={tablePoints.length === 0}
            >
              <Download size={15} />
              Download CSV
            </button>
          </div>
        </div>

        <div className="frontier-table-wrap">
          <table className="frontier-table">
            <thead>
              <tr>
                <th>
                  <button type="button" onClick={() => setSort('model')}>Model</button>
                </th>
                <th>Family</th>
                <th>
                  <button type="button" onClick={() => setSort('parameters')}>Params</button>
                </th>
                <th>Quant.</th>
                <th>
                  <button type="button" onClick={() => setSort('quality')}>Quality ↑</button>
                </th>
                <th>
                  <button type="button" onClick={() => setSort('metric')}>
                    {FRONTIER_METRICS[metric].compactLabel}
                  </button>
                </th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {tablePoints.map((point) => {
                const active = highlightedSignature === point.model_signature;
                return (
                  <tr
                    key={point.model_signature}
                    className={active ? 'active' : ''}
                    onMouseEnter={() => setHoveredSignature(point.model_signature)}
                    onMouseLeave={() => setHoveredSignature(null)}
                    onClick={() =>
                      setSelectedSignature((current) =>
                        current === point.model_signature ? null : point.model_signature,
                      )
                    }
                  >
                    <td><strong>{point.model_key}</strong></td>
                    <td>{point.family ?? '—'}</td>
                    <td>{point.parameters_b == null ? '—' : `${point.parameters_b}B`}</td>
                    <td><span className="frontier-quant-pill">{point.quantization ?? '—'}</span></td>
                    <td><strong>{qualityText(point.quality)}</strong></td>
                    <td>{FRONTIER_METRICS[metric].format(frontierMetricValue(point, metric))}</td>
                    <td>
                      <span className={`frontier-state ${paretoFor(point, metric) ? 'pareto' : 'dominated'}`}>
                        <i />
                        {paretoFor(point, metric) ? 'Pareto' : 'Dominated'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {tablePoints.length === 0 ? (
            <div className="frontier-table-empty">No model matches the current filters.</div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function dimensionValue(point: SensitivityPoint, dimension: string): unknown {
  const [namespace, key] = dimension.split('.', 2);
  const source =
    namespace === 'runtime' ? point.runtime_config : point.inference_config;
  return source[key];
}

function deltaPercent(value: number | null): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function SensitivityChart({
  data,
  dimension,
}: {
  data: SensitivityPoint[];
  dimension: string;
}) {
  const numeric = data
    .map((point) => ({
      point,
      x: dimensionValue(point, dimension),
      y: point.primary_value,
    }))
    .filter(
      (item): item is { point: SensitivityPoint; x: number; y: number } =>
        finite(item.x) && finite(item.y),
    )
    .sort((a, b) => a.x - b.x);

  if (numeric.length < 2) {
    return (
      <div className="experiment-empty">
        At least two completed numeric configurations are needed for this curve.
      </div>
    );
  }

  const minX = Math.min(...numeric.map((item) => item.x));
  const maxX = Math.max(...numeric.map((item) => item.x));
  const minY = Math.min(...numeric.map((item) => item.y));
  const maxY = Math.max(...numeric.map((item) => item.y));
  const cx = (value: number) => scale(value, minX, maxX, 75, 835);
  const cy = (value: number) => scale(value, minY, maxY, 295, 42);
  const path = numeric.map((item) => `${cx(item.x)},${cy(item.y)}`).join(' ');

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    point: SensitivityPoint;
    valX: number;
    valY: number;
  } | null>(null);

  return (
    <div className="experiment-chart-shell" style={{ position: 'relative' }}>
      <svg
        className="experiment-scatter"
        viewBox="0 0 900 350"
        onMouseLeave={() => setTooltip(null)}
      >
        <line x1="72" y1="305" x2="850" y2="305" className="chart-axis" />
        <line x1="72" y1="34" x2="72" y2="305" className="chart-axis" />
        <polyline points={path} className="sensitivity-line" />
        {numeric.map(({ point, x, y }) => {
          const isHovered = tooltip?.point.configuration_id === point.configuration_id;
          return (
            <g
              key={point.configuration_id}
              style={{ cursor: 'pointer' }}
              onMouseEnter={(event) => {
                const rect = event.currentTarget.closest('.experiment-chart-shell')?.getBoundingClientRect();
                if (rect) {
                  setTooltip({
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                    point,
                    valX: x,
                    valY: y,
                  });
                }
              }}
              onMouseMove={(event) => {
                const rect = event.currentTarget.closest('.experiment-chart-shell')?.getBoundingClientRect();
                if (rect) {
                  setTooltip((prev) => prev ? {
                    ...prev,
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                  } : null);
                }
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              <circle
                cx={cx(x)}
                cy={cy(y)}
                r={point.is_baseline ? (isHovered ? 10 : 8) : (isHovered ? 8 : 6)}
                className={point.is_baseline ? 'sensitivity-point baseline' : 'sensitivity-point'}
              />
              <text x={cx(x)} y={327} textAnchor="middle" className="chart-caption">
                {String(x)}
              </text>
            </g>
          );
        })}
        <text x="450" y="346" textAnchor="middle" className="chart-caption">
          {dimension}
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
              className={`dot-tooltip-badge ${tooltip.point.is_baseline ? 'baseline' : 'sensitivity'}`}
            />
            <strong className="dot-tooltip-title">{tooltip.point.label}</strong>
          </div>
          <div className="dot-tooltip-body">
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">Performance</span>
              <span className="dot-tooltip-val highlight">{(tooltip.valY * 100).toFixed(1)}%</span>
            </div>
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">{dimension}</span>
              <span className="dot-tooltip-val">{String(tooltip.valX)}</span>
            </div>
            {tooltip.point.is_baseline ? (
              <div className="dot-tooltip-row">
                <span className="dot-tooltip-label">Config Type</span>
                <span className="dot-tooltip-val is-baseline">Baseline configuration</span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function SensitivityPage() {
  const payload = overview.sensitivity;
  const initialModel = payload?.models[0] ?? '';
  const initialSweep = payload?.sweeps[0] ?? '';
  const initialCapability = payload?.capabilities[0] ?? '';
  const initialDimension =
    payload?.dimensions.find((value) => value !== 'factorial') ?? '';

  const [model, setModel] = useState(initialModel);
  const [sweep, setSweep] = useState(initialSweep);
  const [capability, setCapability] = useState(initialCapability);
  const [dimension, setDimension] = useState(initialDimension);

  const selected = useMemo(
    () =>
      (payload?.points ?? []).filter(
        (point) =>
          point.model_key === model &&
          point.sweep_id === sweep &&
          point.capability_id === capability &&
          (point.is_baseline || point.changed_dimension === dimension),
      ),
    [payload, model, sweep, capability, dimension],
  );

  const ordered = [...selected].sort((a, b) => {
    if (a.is_baseline) return -1;
    if (b.is_baseline) return 1;
    const av = dimensionValue(a, dimension);
    const bv = dimensionValue(b, dimension);
    if (finite(av) && finite(bv)) return av - bv;
    return String(av).localeCompare(String(bv));
  });
  const baseline = ordered.find((point) => point.is_baseline);
  const best = [...ordered]
    .filter((point) => point.primary_value != null)
    .sort((a, b) => Number(b.primary_value) - Number(a.primary_value))[0];

  return (
    <>
      <PageHeader
        eyebrow="Controlled configuration experiments"
        title="Parameter Sensitivity"
        description="Hold the model and benchmark fixed, change one inference or runtime parameter, and measure the quality, latency and memory trade-off against a reproducible baseline."
        actions={
          <>
            <span className="header-chip current">{ordered.length} measured configs</span>
            <span className="header-chip">OVAT + factorial</span>
          </>
        }
      />

      <section className="experiment-controls">
        <label>
          Model
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            {(payload?.models ?? []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Sweep
          <select value={sweep} onChange={(event) => setSweep(event.target.value)}>
            {(payload?.sweeps ?? []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Capability
          <select value={capability} onChange={(event) => setCapability(event.target.value)}>
            {(payload?.capabilities ?? []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Parameter
          <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
            {(payload?.dimensions ?? [])
              .filter((value) => value !== 'factorial')
              .map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
          </select>
        </label>
      </section>

      <section className="experiment-kpis">
        <div className="experiment-kpi">
          <span>Baseline quality</span>
          <strong>
            {baseline?.primary_value == null
              ? '—'
              : `${(baseline.primary_value * 100).toFixed(1)}%`}
          </strong>
          <small>{baseline?.label ?? 'No baseline projected'}</small>
        </div>
        <div className="experiment-kpi">
          <span>Best measured quality</span>
          <strong>
            {best?.primary_value == null
              ? '—'
              : `${(best.primary_value * 100).toFixed(1)}%`}
          </strong>
          <small>{best?.label ?? 'No completed point'}</small>
        </div>
        <div className="experiment-kpi">
          <span>Best quality delta</span>
          <strong>{points(best?.quality_delta_vs_baseline)}</strong>
          <small>versus the sweep baseline</small>
        </div>
      </section>

      <section className="experiment-panel">
        <div className="experiment-panel-heading">
          <div>
            <h2>{dimension || 'Sensitivity curve'}</h2>
            <p>
              Quality is the capability primary metric. Runtime deltas are derived
              from the same configuration run evidence.
            </p>
          </div>
        </div>
        <SensitivityChart data={ordered} dimension={dimension} />
      </section>

      <section className="experiment-panel">
        <div className="experiment-panel-heading">
          <div>
            <h2>Configuration evidence</h2>
            <p>Baseline-relative deltas make the cost of each parameter change explicit.</p>
          </div>
        </div>
        <div className="experiment-table-wrap">
          <table className="experiment-table">
            <thead>
              <tr>
                <th>Configuration</th>
                <th>{dimension || 'Value'}</th>
                <th>Quality</th>
                <th>Δ quality</th>
                <th>P50 latency</th>
                <th>Δ latency</th>
                <th>Peak RAM</th>
                <th>Δ RAM</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((point) => (
                <tr key={point.configuration_id}>
                  <td>
                    <strong>{point.is_baseline ? 'Baseline' : point.label}</strong>
                  </td>
                  <td>{String(dimensionValue(point, dimension) ?? '—')}</td>
                  <td>
                    {point.primary_value == null
                      ? '—'
                      : `${(point.primary_value * 100).toFixed(1)}%`}
                  </td>
                  <td>{points(point.quality_delta_vs_baseline)}</td>
                  <td>{milliseconds(point.latency_p50_ms)}</td>
                  <td>{deltaPercent(point.latency_delta_pct_vs_baseline)}</td>
                  <td>{bytes(point.process_rss_bytes_peak)}</td>
                  <td>{deltaPercent(point.rss_delta_pct_vs_baseline)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {ordered.length === 0 ? (
          <div className="experiment-empty">
            No projected sensitivity run matches this selection yet.
          </div>
        ) : null}
      </section>
    </>
  );
}
