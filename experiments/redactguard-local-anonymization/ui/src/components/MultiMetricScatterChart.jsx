import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { uiConfig } from "../config/uiConfig";
import { formatMs, formatPercent, micro, percentValue } from "../utils/formatters";

/**
 * Helper to extract and format a metric value according to its type.
 */
function extractMetricValue(metricKey, summary, latencySummary) {
  const metricDef = uiConfig.scatterMetrics[metricKey];
  if (!metricDef) return null;

  let raw = null;
  if (metricKey === "latency_p95_ms") {
    raw =
      latencySummary?.latency_p95_ms ??
      latencySummary?.p95_ms ??
      summary?.latency_p95_ms ??
      null;
  } else if (metricKey === "latency_p50_ms") {
    raw =
      latencySummary?.latency_p50_ms ??
      latencySummary?.p50_ms ??
      summary?.latency_p50_ms ??
      null;
  } else {
    raw = summary?.[metricKey] ?? null;
  }

  if (raw === null || raw === undefined || Number.isNaN(Number(raw))) {
    return null;
  }

  if (metricDef.type === "percent") {
    return percentValue(raw);
  }
  return Number(raw);
}

/**
 * Helper to format a metric value for display (tooltips, axis, labels).
 */
function formatValueByMetric(metricKey, value) {
  const metricDef = uiConfig.scatterMetrics[metricKey];
  if (value === null || value === undefined) return "—";
  if (metricDef?.type === "percent") return formatPercent(value);
  if (metricDef?.type === "ms") return formatMs(value);
  return String(value);
}

/**
 * Multi-metric scatter plot allowing users to plot any two performance metrics against each other.
 */
export function MultiMetricScatterChart({ detail, selectedModel, onSelectModel }) {
  const [xMetricKey, setXMetricKey] = useState("latency_p95_ms");
  const [yMetricKey, setYMetricKey] = useState("pii_recall");

  const xDef = uiConfig.scatterMetrics[xMetricKey] ?? uiConfig.scatterMetrics.latency_p95_ms;
  const yDef = uiConfig.scatterMetrics[yMetricKey] ?? uiConfig.scatterMetrics.pii_recall;

  // Compile scatter plot data across all models present in detail
  const data = useMemo(() => {
    if (!detail?.metrics) return [];

    const models = Object.keys(detail.metrics);
    return models
      .map((model, index) => {
        const summary = micro(detail.metrics[model]);
        const latencySummary = micro(detail.latency?.metrics?.[model]);
        const evidence = detail.evidence?.[model];

        const x = extractMetricValue(xMetricKey, summary, latencySummary);
        const y = extractMetricValue(yMetricKey, summary, latencySummary);

        if (x === null || y === null) return null;

        const color = uiConfig.modelColors[index % uiConfig.modelColors.length];

        return {
          model,
          x,
          y,
          color,
          status: evidence?.status ?? (summary ? "complete" : "unknown"),
          cases: evidence?.cases ?? summary?.cases ?? null,
          source: evidence?.suiteId || evidence?.runId || "run",
        };
      })
      .filter(Boolean);
  }, [detail, xMetricKey, yMetricKey]);

  // Swap X and Y axes
  const handleSwapAxes = () => {
    const temp = xMetricKey;
    setXMetricKey(yMetricKey);
    setYMetricKey(temp);
  };

  // Apply a pre-configured comparison preset
  const handleApplyPreset = (preset) => {
    setXMetricKey(preset.x);
    setYMetricKey(preset.y);
  };

  const metricOptions = Object.values(uiConfig.scatterMetrics);

  return (
    <div className="multi-scatter-container">
      {/* Metric Axis Selectors & Preset Controls */}
      <div className="scatter-toolbar">
        <div className="scatter-selectors">
          <label className="axis-control">
            <span className="eyebrow">Asse X</span>
            <select
              value={xMetricKey}
              onChange={(e) => setXMetricKey(e.target.value)}
              aria-label="Metrica Asse X"
            >
              {metricOptions.map((opt) => (
                <option key={`x-${opt.key}`} value={opt.key}>
                  {opt.label} ({opt.unit.trim()})
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="swap-axes-btn"
            onClick={handleSwapAxes}
            title="Inverti gli assi X e Y"
            aria-label="Inverti assi"
          >
            ⇄
          </button>

          <label className="axis-control">
            <span className="eyebrow">Asse Y</span>
            <select
              value={yMetricKey}
              onChange={(e) => setYMetricKey(e.target.value)}
              aria-label="Metrica Asse Y"
            >
              {metricOptions.map((opt) => (
                <option key={`y-${opt.key}`} value={opt.key}>
                  {opt.label} ({opt.unit.trim()})
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Quick Presets */}
        <div className="scatter-presets">
          <span className="eyebrow">Preset:</span>
          {uiConfig.scatterPresets.map((preset) => {
            const isActive = xMetricKey === preset.x && yMetricKey === preset.y;
            return (
              <button
                type="button"
                key={preset.id}
                className={`preset-pill ${isActive ? "active" : ""}`}
                onClick={() => handleApplyPreset(preset)}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Scatter Chart */}
      {!data.length ? (
        <div className="chart-empty">
          Nessun dato comparabile disponibile per la combinazione {xDef.label} vs {yDef.label}.
        </div>
      ) : (
        <div className="scatter-chart-wrapper">
          <ResponsiveContainer width="100%" height={uiConfig.charts.scatterHeight}>
            <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis
                type="number"
                dataKey="x"
                name={xDef.label}
                unit={xDef.unit}
                domain={xDef.domain === "auto" ? ["auto", "auto"] : xDef.domain}
                tickLine={false}
                axisLine={false}
                label={{
                  value: `${xDef.label} (${xDef.unit.trim()})`,
                  position: "insideBottom",
                  offset: -12,
                  fill: "var(--muted)",
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={yDef.label}
                unit={yDef.unit}
                domain={yDef.domain === "auto" ? ["auto", "auto"] : yDef.domain}
                tickLine={false}
                axisLine={false}
                width={55}
                label={{
                  value: `${yDef.label} (${yDef.unit.trim()})`,
                  angle: -90,
                  position: "insideLeft",
                  offset: 5,
                  fill: "var(--muted)",
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const item = payload[0].payload;
                  return (
                    <div className="scatter-custom-tooltip">
                      <div className="tooltip-header">
                        <span
                          className="model-swatch"
                          style={{ backgroundColor: item.color }}
                        />
                        <strong>{item.model}</strong>
                      </div>
                      <div className="tooltip-row">
                        <span>{xDef.label}:</span>
                        <strong>{formatValueByMetric(xMetricKey, item.x)}</strong>
                      </div>
                      <div className="tooltip-row">
                        <span>{yDef.label}:</span>
                        <strong>{formatValueByMetric(yMetricKey, item.y)}</strong>
                      </div>
                      {item.cases !== null ? (
                        <div className="tooltip-meta">
                          <small>Casi testati: {item.cases}</small>
                        </div>
                      ) : null}
                    </div>
                  );
                }}
              />
              <Scatter
                name="Modelli"
                data={data}
                onClick={(entry) => onSelectModel?.(entry.model)}
                style={{ cursor: "pointer" }}
              >
                {data.map((entry) => (
                  <Cell
                    key={`cell-${entry.model}`}
                    fill={entry.color}
                    stroke={selectedModel === entry.model ? "var(--text)" : entry.color}
                    strokeWidth={selectedModel === entry.model ? 3 : 1}
                    r={selectedModel === entry.model ? 8 : 6}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>

          {/* Model Points Legend & Comparison Bar */}
          <div className="scatter-model-chips">
            {data.map((item) => (
              <button
                type="button"
                key={item.model}
                className={`model-chip ${selectedModel === item.model ? "model-chip--selected" : ""}`}
                onClick={() => onSelectModel?.(item.model)}
              >
                <span className="chip-dot" style={{ backgroundColor: item.color }} />
                <span className="chip-name">{item.model}</span>
                <span className="chip-values">
                  {formatValueByMetric(xMetricKey, item.x)} · {formatValueByMetric(yMetricKey, item.y)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default MultiMetricScatterChart;
