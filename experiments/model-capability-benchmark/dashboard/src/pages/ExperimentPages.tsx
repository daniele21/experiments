import { useMemo, useState } from 'react';
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

const FRONTIER_METRICS: Record<
  FrontierMetric,
  { label: string; format: (value: number | null) => string }
> = {
  parameters_b: {
    label: 'Parameters',
    format: (value) => value == null ? '—' : `${value}B`,
  },
  artifact_size_bytes: { label: 'Artifact size', format: bytes },
  peak_rss_bytes: { label: 'Peak RAM', format: bytes },
  latency_p50_ms: { label: 'P50 latency', format: milliseconds },
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

function FrontierChart({
  points: data,
  metric,
  mode,
}: {
  points: FrontierPoint[];
  metric: FrontierMetric;
  mode: FrontierMode;
}) {
  const pointsWithData = data.filter(
    (point) => finite(point[metric]) && finite(point.quality),
  );
  if (pointsWithData.length === 0) {
    return (
      <div className="experiment-empty">
        Run and project local benchmarks to populate this frontier.
      </div>
    );
  }

  const xs = pointsWithData.map((point) => Number(point[metric]));
  const ys = pointsWithData.map((point) => Number(point.quality));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const groups = new Map<string, FrontierPoint[]>();
  for (const point of pointsWithData) {
    const key =
      mode === 'family' ? point.family : point.compression_group;
    if (!key) continue;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  }

  const x = (point: FrontierPoint) =>
    scale(Number(point[metric]), minX, maxX, 72, 842);
  const y = (point: FrontierPoint) =>
    scale(Number(point.quality), minY, maxY, 300, 42);

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    point: FrontierPoint;
  } | null>(null);

  return (
    <div className="experiment-chart-shell" style={{ position: 'relative' }}>
      <svg
        className="experiment-scatter"
        viewBox="0 0 900 350"
        role="img"
        aria-label="Quality versus deployment resource Pareto frontier"
        onMouseLeave={() => setTooltip(null)}
      >
        <line x1="72" y1="310" x2="850" y2="310" className="chart-axis" />
        <line x1="72" y1="34" x2="72" y2="310" className="chart-axis" />
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
              className={`frontier-family-line family-line-${index % 6}`}
            />
          );
        })}
        {pointsWithData.map((point) => {
          const pareto = paretoFor(point, metric);
          const radius = point.parameters_b
            ? Math.max(5, Math.min(11, 4 + Math.sqrt(point.parameters_b)))
            : 6;
          const isHovered = tooltip?.point.model_signature === point.model_signature;
          return (
            <g
              key={point.model_signature}
              style={{ cursor: 'pointer' }}
              onMouseEnter={(event) => {
                const rect = event.currentTarget.closest('.experiment-chart-shell')?.getBoundingClientRect();
                if (rect) {
                  setTooltip({
                    x: event.clientX - rect.left,
                    y: event.clientY - rect.top,
                    point,
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
                cx={x(point)}
                cy={y(point)}
                r={isHovered ? radius + 2 : radius}
                className={pareto ? 'frontier-point pareto' : 'frontier-point dominated'}
              />
              <text
                x={x(point) + radius + 4}
                y={y(point) - 5}
                className="frontier-label"
              >
                {point.model_key}
              </text>
            </g>
          );
        })}
        <text x="450" y="342" textAnchor="middle" className="chart-caption">
          {FRONTIER_METRICS[metric].label} · lower is better
        </text>
        <text
          x="18"
          y="172"
          textAnchor="middle"
          transform="rotate(-90 18 172)"
          className="chart-caption"
        >
          Quality · higher is better
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
              className={`dot-tooltip-badge ${paretoFor(tooltip.point, metric) ? 'pareto' : 'dominated'}`}
            />
            <strong className="dot-tooltip-title">{tooltip.point.model_key}</strong>
          </div>
          <div className="dot-tooltip-body">
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">Quality Score</span>
              <span className="dot-tooltip-val highlight">{score(tooltip.point.quality)}</span>
            </div>
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">{FRONTIER_METRICS[metric].label}</span>
              <span className="dot-tooltip-val">
                {FRONTIER_METRICS[metric].format(tooltip.point[metric])}
              </span>
            </div>
            {tooltip.point.family ? (
              <div className="dot-tooltip-row">
                <span className="dot-tooltip-label">Family</span>
                <span className="dot-tooltip-val">{tooltip.point.family}</span>
              </div>
            ) : null}
            <div className="dot-tooltip-row">
              <span className="dot-tooltip-label">Status</span>
              <span className={`dot-tooltip-val ${paretoFor(tooltip.point, metric) ? 'is-pareto' : ''}`}>
                {paretoFor(tooltip.point, metric) ? 'Pareto Frontier' : 'Dominated'}
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function FrontierPage() {
  const payload = overview.frontier;
  const [metric, setMetric] = useState<FrontierMetric>('parameters_b');
  const [mode, setMode] = useState<FrontierMode>('family');
  const [family, setFamily] = useState('all');

  const localPoints = useMemo(
    () =>
      (payload?.points ?? []).filter(
        (point) =>
          point.deployment === 'local' &&
          (family === 'all' || point.family === family),
      ),
    [payload, family],
  );
  const paretoCount = localPoints.filter((point) => paretoFor(point, metric)).length;

  return (
    <>
      <PageHeader
        eyebrow="Local deployment frontier"
        title="Pareto Frontier"
        description="See where model families, parameter counts and quantizations buy real quality — and where extra size, RAM or latency stops paying back."
        actions={
          <>
            <span className="header-chip current">{paretoCount} Pareto-efficient</span>
            <span className="header-chip">{localPoints.length} local configs</span>
          </>
        }
      />

      <section className="experiment-controls">
        <label>
          X axis
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value as FrontierMetric)}
          >
            {Object.entries(FRONTIER_METRICS).map(([key, config]) => (
              <option key={key} value={key}>{config.label}</option>
            ))}
          </select>
        </label>
        <label>
          Connect
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as FrontierMode)}
          >
            <option value="family">Model family scaling</option>
            <option value="compression">Compression variants</option>
          </select>
        </label>
        <label>
          Family
          <select value={family} onChange={(event) => setFamily(event.target.value)}>
            <option value="all">All families</option>
            {(payload?.families ?? []).map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
      </section>

      <section className="experiment-panel">
        <div className="experiment-panel-heading">
          <div>
            <h2>
              Quality × {FRONTIER_METRICS[metric].label}
            </h2>
            <p>
              Solid points sit on the selected Pareto frontier. Faded points are
              dominated by another measured configuration.
            </p>
          </div>
          <div className="experiment-legend">
            <span><i className="legend-dot pareto" /> Pareto</span>
            <span><i className="legend-dot dominated" /> Dominated</span>
          </div>
        </div>
        <FrontierChart points={localPoints} metric={metric} mode={mode} />
      </section>

      <section className="experiment-panel">
        <div className="experiment-panel-heading">
          <div>
            <h2>Frontier evidence</h2>
            <p>Family and compression metadata stay visible next to measured quality and resource cost.</p>
          </div>
        </div>
        <div className="experiment-table-wrap">
          <table className="experiment-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Family</th>
                <th>Params</th>
                <th>Quant.</th>
                <th>Quality</th>
                <th>{FRONTIER_METRICS[metric].label}</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {[...localPoints]
                .filter((point) => finite(point.quality))
                .sort((a, b) => Number(b.quality) - Number(a.quality))
                .map((point) => (
                  <tr key={point.model_signature}>
                    <td><strong>{point.model_key}</strong></td>
                    <td>{point.family ?? '—'}</td>
                    <td>{point.parameters_b == null ? '—' : `${point.parameters_b}B`}</td>
                    <td>{point.quantization ?? '—'}</td>
                    <td>{score(point.quality)}</td>
                    <td>{FRONTIER_METRICS[metric].format(point[metric])}</td>
                    <td>
                      <span className={paretoFor(point, metric) ? 'state-pill pareto' : 'state-pill dominated'}>
                        {paretoFor(point, metric) ? 'Pareto' : 'Dominated'}
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
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
