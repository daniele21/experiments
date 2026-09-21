/**
 * CostAccuracyChart.tsx
 *
 * Flagship scatter plot visualizing the Cost vs Accuracy Frontier.
 *
 * Compares API cost per 1,000 requests (USD) against intent classification accuracy.
 * Highlights:
 *  - Dedicated $0 Free On-Device zone for Apple Silicon hardware runs
 *  - Pareto frontier curve across paid cloud APIs
 *  - High-definition 960x460 canvas with collision-free label layouts
 *  - Flagship header with economic status badges and interactive legend
 *  - Glassmorphic hover tooltips with detailed performance and pricing metrics
 *  - Strategic economic takeaway footer
 */

import React, { useState } from 'react';
import type { OverviewRow } from '../../types/benchmark';
import { getSeriesColor, formatMoney, formatPct } from '../../config/theme';
import { Coins, DollarSign, TrendingUp } from 'lucide-react';

interface CostAccuracyChartProps {
  overview: OverviewRow[];
  selectedSeries: Set<string>;
}

interface HoveredPoint {
  row: OverviewRow;
  x: number;
  y: number;
}

export const CostAccuracyChart: React.FC<CostAccuracyChartProps> = ({
  overview,
  selectedSeries,
}) => {
  const [hovered, setHovered] = useState<HoveredPoint | null>(null);

  const visible = overview.filter(
    (r) => selectedSeries.has(r.series) || (r.series_id && selectedSeries.has(r.series_id))
  );
  if (visible.length === 0) return null;

  // ── High-Resolution Canvas Dimensions ────────────────────────────
  const width = 960;
  const height = 460;
  const marginTop = 40;
  const marginRight = 55;
  const marginBottom = 65;
  const marginLeft = 75;

  const plotWidth = width - marginLeft - marginRight;
  const plotHeight = height - marginTop - marginBottom;

  // ── Separate free ($0) on-device models from paid cloud APIs ──────
  const paidModels = visible.filter((r) => r.cost_per_1k_requests_usd > 0);
  const freeModels = visible.filter((r) => r.cost_per_1k_requests_usd === 0);

  // ── Domain ───────────────────────────────────────────────────────
  const maxCost =
    paidModels.length > 0
      ? Math.max(
          0.1,
          Math.ceil(Math.max(...paidModels.map((r) => r.cost_per_1k_requests_usd)) * 10) / 10 + 0.05
        )
      : 0.5;

  // Generous left zone reserved for $0 local models on host hardware
  const freeZoneWidth = 260;
  const paidPlotWidth = plotWidth - freeZoneWidth;

  const maxAcc = 1.05; // Headroom so 100% accuracy never clips top border
  const minAcc = 0.0;

  const getCostX = (cost: number): number => {
    if (cost === 0) return marginLeft + 28;
    return marginLeft + freeZoneWidth + 30 + (cost / maxCost) * (paidPlotWidth - 30);
  };

  const getAccY = (acc: number): number =>
    height - marginBottom - ((acc - minAcc) / (maxAcc - minAcc)) * plotHeight;

  // ── Calculate collision-free Y positions for free models ──────────
  const sortedFreeForLayout = freeModels
    .map((row) => ({
      series: row.series,
      actualY: getAccY(row.accuracy),
      layoutY: getAccY(row.accuracy),
    }))
    .sort((a, b) => a.actualY - b.actualY); // top of chart first

  const minVerticalGap = 24;
  for (let i = 1; i < sortedFreeForLayout.length; i++) {
    const prev = sortedFreeForLayout[i - 1];
    const curr = sortedFreeForLayout[i];
    if (curr.layoutY - prev.layoutY < minVerticalGap) {
      curr.layoutY = prev.layoutY + minVerticalGap;
    }
  }

  const freeLabelYMap = new Map<string, { actualY: number; layoutY: number }>();
  sortedFreeForLayout.forEach((item) => {
    freeLabelYMap.set(item.series, item);
  });

  // ── Grid Ticks ───────────────────────────────────────────────────
  const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];
  const xTickCount = 4;
  const xTicks = Array.from({ length: xTickCount + 1 }, (_, i) =>
    parseFloat(((maxCost / xTickCount) * i).toFixed(3))
  );

  // ── Pareto Frontier across paid models ───────────────────────────
  const sortedPaid = [...paidModels].sort(
    (a, b) => a.cost_per_1k_requests_usd - b.cost_per_1k_requests_usd
  );
  const paretoPoints: OverviewRow[] = [];
  let currentMaxAcc = -1;
  for (const row of sortedPaid) {
    if (row.accuracy > currentMaxAcc) {
      paretoPoints.push(row);
      currentMaxAcc = row.accuracy;
    }
  }

  const paretoPath =
    paretoPoints.length > 1
      ? paretoPoints
          .map(
            (p, i) =>
              `${i === 0 ? 'M' : 'L'} ${getCostX(p.cost_per_1k_requests_usd)} ${getAccY(p.accuracy)}`
          )
          .join(' ')
      : '';

  // ── Clean short label helper ─────────────────────────────────────
  const shortLabel = (series: string): string =>
    series
      .replace('Korgis · ', '')
      .replace(' Q4_K_M', '')
      .replace(' Q8_0', ' Q8')
      .replace('Jev · ', 'Jev ')
      .replace('nemotron-nano-', 'n-');

  return (
    <div className="card frontier-flagship-card">
      {/* Flagship Header */}
      <div className="card-header">
        <div className="card-title-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="frontier-icon-badge frontier-icon-cost">
              <Coins size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 className="card-title" style={{ margin: 0 }}>Cost vs Accuracy Frontier</h3>
                <span className="frontier-badge-pulse cost-pulse">
                  <DollarSign size={11} style={{ marginRight: '3px' }} />
                  Primary Economic Pareto Framework
                </span>
              </div>
              <p className="card-subtitle" style={{ margin: '4px 0 0 0' }}>
                Quantifies cost efficiency: $0 marginal fee for on-device hardware inference vs cloud token billing.
              </p>
            </div>
          </div>

          <div className="frontier-header-legend">
            <div className="legend-indicator-item">
              <span className="legend-zone-swatch" style={{ background: 'rgba(5, 150, 105, 0.15)', borderColor: '#059669' }} />
              <span>$0 On-Device Host Hardware</span>
            </div>
            <div className="legend-indicator-item">
              <span className="legend-dash-line" style={{ background: 'linear-gradient(90deg, #4f46e5, #06b6d4)' }} />
              <span>Cloud API Pareto Curve</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{ position: 'relative', overflow: 'visible', padding: '8px 0' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          {/* SVG Definitions */}
          <defs>
            <linearGradient id="cost-pareto-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="cost-pareto-area-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.10" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.01" />
            </linearGradient>
            <linearGradient id="free-zone-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Free Zone Background Band */}
          <rect
            x={marginLeft}
            y={marginTop}
            width={freeZoneWidth}
            height={plotHeight}
            fill="url(#free-zone-grad)"
            rx={8}
          />

          {/* Free Zone Header Callout */}
          <g transform={`translate(${marginLeft + freeZoneWidth / 2}, ${marginTop + 18})`}>
            <text
              x={0}
              y={0}
              textAnchor="middle"
              style={{
                fontSize: '11px',
                fontWeight: 800,
                fill: 'var(--success, #059669)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              ★ $0 · Free On-Device Hardware
            </text>
            <text
              x={0}
              y={14}
              textAnchor="middle"
              style={{
                fontSize: '9.5px',
                fontWeight: 600,
                fill: 'var(--text-muted)',
                letterSpacing: '0.02em',
              }}
            >
              Apple M3 Pro · 36GB RAM · Zero Cloud Fee
            </text>
          </g>

          {/* Separator Dashed Line */}
          <line
            x1={marginLeft + freeZoneWidth}
            y1={marginTop}
            x2={marginLeft + freeZoneWidth}
            y2={height - marginBottom}
            stroke="#059669"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            opacity={0.35}
          />

          {/* Horizontal Grid Lines */}
          {yTicks.map((acc) => {
            const y = getAccY(acc);
            return (
              <g key={`y-${acc}`}>
                <line
                  x1={marginLeft}
                  y1={y}
                  x2={width - marginRight}
                  y2={y}
                  className="chart-grid-line"
                />
                <text
                  x={marginLeft - 12}
                  y={y + 4}
                  textAnchor="end"
                  className="chart-axis-text"
                  style={{ fontWeight: 600 }}
                >
                  {`${Math.round(acc * 100)}%`}
                </text>
              </g>
            );
          })}

          {/* Vertical Grid Lines (Paid Zone) */}
          {xTicks.map((cost) => {
            if (cost === 0) return null; // Cost 0 is handled by the Free Zone
            const x = getCostX(cost);
            return (
              <g key={`x-${cost}`}>
                <line
                  x1={x}
                  y1={marginTop}
                  x2={x}
                  y2={height - marginBottom}
                  className="chart-grid-line"
                />
                <text
                  x={x}
                  y={height - marginBottom + 24}
                  textAnchor="middle"
                  className="chart-axis-text"
                  style={{ fontWeight: 600 }}
                >
                  {`$${cost.toFixed(2)}`}
                </text>
              </g>
            );
          })}

          {/* Axes */}
          <line
            x1={marginLeft}
            y1={marginTop}
            x2={marginLeft}
            y2={height - marginBottom}
            className="chart-axis-line"
          />
          <line
            x1={marginLeft}
            y1={height - marginBottom}
            x2={width - marginRight}
            y2={height - marginBottom}
            className="chart-axis-line"
          />

          {/* Axis Titles */}
          <text
            x={marginLeft + plotWidth / 2}
            y={height - 14}
            textAnchor="middle"
            className="chart-axis-title"
            style={{ fontWeight: 700, letterSpacing: '0.04em' }}
          >
            Inference Cost per 1,000 Routing Requests (USD)
          </text>
          <text
            x={-(marginTop + plotHeight / 2)}
            y={22}
            transform="rotate(-90)"
            textAnchor="middle"
            className="chart-axis-title"
            style={{ fontWeight: 700, letterSpacing: '0.04em' }}
          >
            Intent Classification Accuracy (%)
          </text>

          {/* Shaded Area under Paid Pareto Curve */}
          {paretoPoints.length > 1 && (
            <path
              d={`${paretoPath} L ${getCostX(paretoPoints[paretoPoints.length - 1].cost_per_1k_requests_usd)} ${height - marginBottom} L ${getCostX(paretoPoints[0].cost_per_1k_requests_usd)} ${height - marginBottom} Z`}
              fill="url(#cost-pareto-area-grad)"
            />
          )}

          {/* Paid Pareto Frontier Line */}
          {paretoPath && (
            <path
              d={paretoPath}
              fill="none"
              stroke="url(#cost-pareto-grad)"
              strokeWidth="3"
              strokeDasharray="6 4"
              opacity="0.8"
            />
          )}

          {/* Free Models: Diamond Markers with Collision-Free Layout */}
          {freeModels.map((row, idx) => {
            const seriesIndex = overview.findIndex((r) => r.series === row.series);
            const color = getSeriesColor(row.series, seriesIndex);
            const markerX = marginLeft + 24;
            const actualCy = getAccY(row.accuracy);
            const layoutInfo = freeLabelYMap.get(row.series) || { actualY: actualCy, layoutY: actualCy };
            const labelY = layoutInfo.layoutY;
            const isHovered = hovered?.row.series === row.series;
            const size = isHovered ? 8 : 6;
            const labelX = marginLeft + 38;

            return (
              <g
                key={`free-${idx}`}
                onMouseEnter={() => setHovered({ row, x: markerX, y: actualCy })}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Glow ring on hover */}
                {isHovered && (
                  <circle cx={markerX} cy={actualCy} r={16} fill={color} opacity={0.16} />
                )}

                {/* Connector line if label was offset vertically to avoid collision */}
                {Math.abs(labelY - actualCy) > 3 && (
                  <path
                    d={`M ${markerX + 7} ${actualCy} L ${labelX - 4} ${labelY}`}
                    stroke={color}
                    strokeWidth={1}
                    strokeDasharray="2 2"
                    opacity={0.65}
                  />
                )}

                {/* Diamond shape */}
                <rect
                  x={markerX - size}
                  y={actualCy - size}
                  width={size * 2}
                  height={size * 2}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={2.5}
                  transform={`rotate(45, ${markerX}, ${actualCy})`}
                  style={{
                    filter: isHovered ? `drop-shadow(0 0 10px ${color})` : 'drop-shadow(0 1px 3px rgba(0,0,0,0.25))',
                    transition: 'all 0.15s ease',
                  }}
                />

                {/* Label */}
                <text
                  x={labelX}
                  y={labelY + 4}
                  style={{
                    fontSize: isHovered ? '11px' : '10.5px',
                    fontWeight: isHovered ? 800 : 600,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                    pointerEvents: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {shortLabel(row.series)} ({formatPct(row.accuracy)})
                </text>
              </g>
            );
          })}

          {/* Paid Models: Circle Markers */}
          {paidModels.map((row, idx) => {
            const seriesIndex = overview.findIndex((r) => r.series === row.series);
            const color = getSeriesColor(row.series, seriesIndex);
            const cx = getCostX(row.cost_per_1k_requests_usd);
            const cy = getAccY(row.accuracy);
            const isHovered = hovered?.row.series === row.series;

            return (
              <g
                key={`paid-${idx}`}
                onMouseEnter={() => setHovered({ row, x: cx, y: cy })}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Glow ring on hover */}
                {isHovered && (
                  <circle cx={cx} cy={cy} r={18} fill={color} opacity={0.16} />
                )}

                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 8.5 : 6.5}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={2.5}
                  style={{
                    filter: isHovered ? `drop-shadow(0 0 10px ${color})` : 'drop-shadow(0 1px 3px rgba(0,0,0,0.25))',
                    transition: 'r 0.15s ease, filter 0.15s ease',
                  }}
                />

                {/* Label */}
                <text
                  x={cx}
                  y={cy - 14}
                  textAnchor="middle"
                  style={{
                    fontSize: isHovered ? '12px' : '11px',
                    fontWeight: isHovered ? 800 : 650,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                    pointerEvents: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {shortLabel(row.series)} ({formatPct(row.accuracy)})
                </text>
              </g>
            );
          })}
        </svg>

        {/* Glassmorphic Hover Tooltip */}
        {hovered && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hovered.x / width) * 100}%`,
              top: `${(hovered.y / height) * 100}%`,
              transform: 'translate(-50%, -120%)',
              pointerEvents: 'none',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 800, fontSize: '13px', marginBottom: '4px', color: '#ffffff' }}>
              {hovered.row.series}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '11px', marginTop: '6px' }}>
              <div>
                <span style={{ color: '#94a3b8' }}>Accuracy: </span>
                <strong style={{ color: '#ffffff' }}>{formatPct(hovered.row.accuracy)}</strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Cost / 1k: </span>
                <strong style={{ color: hovered.row.cost_per_1k_requests_usd === 0 ? '#34d399' : '#38bdf8' }}>
                  {hovered.row.cost_per_1k_requests_usd === 0
                    ? '$0.00 (Free)'
                    : formatMoney(hovered.row.cost_per_1k_requests_usd, 4)}
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Latency p50: </span>
                <strong style={{ color: '#e2e8f0' }}>{Math.round(hovered.row.latency_p50_ms)} ms</strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Thinking: </span>
                <strong style={{ color: hovered.row.thinking_mode === 'on' ? '#c084fc' : '#e2e8f0' }}>
                  {hovered.row.thinking_mode === 'on' ? 'ON (Reasoning)' : 'Direct'}
                </strong>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Flagship Strategic Takeaway Callout */}
      <div className="frontier-card-footer">
        <div className="frontier-insight-pill">
          <span className="insight-badge" style={{ background: '#ecfdf5', color: '#059669', borderColor: '#a7f3d0' }}>
            <TrendingUp size={12} style={{ marginRight: '4px' }} />
            Economic Verdict
          </span>
          <span className="insight-text">
            On-device models run at <strong>$0.00 marginal API cost</strong> on Apple Silicon (M3 Pro 36GB), avoiding recurring token expenses and third-party data exposure.
            For cloud inference, <strong>GPT-5.6 Luna</strong> sets the external accuracy ceiling (79.2%) at <strong>$0.19 / 1k requests</strong>.
          </span>
        </div>
      </div>
    </div>
  );
};
