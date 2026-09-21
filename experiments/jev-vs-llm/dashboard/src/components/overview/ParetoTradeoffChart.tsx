import React, { useState } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';

interface ParetoTradeoffChartProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
}

export const ParetoTradeoffChart: React.FC<ParetoTradeoffChartProps> = ({
  entries,
  selectedSeries,
}) => {
  const [hoveredEntry, setHoveredEntry] = useState<{
    entry: LeaderboardEntry;
    x: number;
    y: number;
  } | null>(null);

  const visibleEntries = entries.filter((e) => selectedSeries.has(e.series));
  if (visibleEntries.length === 0) return null;

  // Chart dimensions
  const width = 800;
  const height = 400;
  const marginTop = 30;
  const marginRight = 40;
  const marginBottom = 60;
  const marginLeft = 60;

  const plotWidth = width - marginLeft - marginRight;
  const plotHeight = height - marginTop - marginBottom;

  // Compute domain
  const latencies = visibleEntries.map((e) => e.latency_p50_ms);
  const maxLat = Math.max(9000, Math.ceil(Math.max(...latencies) / 1000) * 1000);
  const maxAcc = 0.8; // 80% cap for clear vertical resolution

  const getX = (lat: number) => marginLeft + (lat / maxLat) * plotWidth;
  const getY = (acc: number) => height - marginBottom - (acc / maxAcc) * plotHeight;

  // Determine Pareto Frontier points (sorted by latency ascending, filter strictly increasing accuracy)
  const sortedByLat = [...visibleEntries].sort((a, b) => a.latency_p50_ms - b.latency_p50_ms);
  const paretoPoints: LeaderboardEntry[] = [];
  let currentMaxAcc = -1;
  for (const entry of sortedByLat) {
    if (entry.accuracy > currentMaxAcc) {
      paretoPoints.push(entry);
      currentMaxAcc = entry.accuracy;
    }
  }

  const paretoPath =
    paretoPoints.length > 1
      ? paretoPoints
          .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(p.latency_p50_ms)} ${getY(p.accuracy)}`)
          .join(' ')
      : '';

  const xTicks = [0, 2000, 4000, 6000, 8000];
  const yTicks = [0, 0.2, 0.4, 0.6, 0.8];

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Accuracy vs latency (Pareto Frontier)</h3>
        <p className="chart-desc">
          Upper-left is preferable: higher correctness with lower latency. The dashed line highlights
          the Pareto efficiency frontier. Hover over any point to inspect details.
        </p>
      </div>

      <div className="chart-wrapper" style={{ position: 'relative' }}>
        <svg viewBox={`0 0 ${width} ${height}`} className="interactive-chart">
          {/* Horizontal Grid lines */}
          {yTicks.map((acc) => {
            const y = getY(acc);
            return (
              <g key={acc}>
                <line
                  x1={marginLeft}
                  y1={y}
                  x2={width - marginRight}
                  y2={y}
                  className="chart-grid-line"
                />
                <text
                  x={marginLeft - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="chart-axis-text"
                >
                  {`${Math.round(acc * 100)}%`}
                </text>
              </g>
            );
          })}

          {/* Vertical Grid lines */}
          {xTicks.map((lat) => {
            const x = getX(lat);
            return (
              <g key={lat}>
                <line
                  x1={x}
                  y1={marginTop}
                  x2={x}
                  y2={height - marginBottom}
                  className="chart-grid-line"
                />
                <text
                  x={x}
                  y={height - marginBottom + 20}
                  textAnchor="middle"
                  className="chart-axis-text"
                >
                  {lat === 0 ? '0' : `${lat / 1000}s`}
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
            y={height - marginBottom + 42}
            textAnchor="middle"
            className="chart-axis-title"
          >
            p50 Latency (milliseconds / seconds)
          </text>

          <text
            x={-height / 2}
            y={20}
            transform="rotate(-90)"
            textAnchor="middle"
            className="chart-axis-title"
          >
            Intent Accuracy
          </text>

          {/* Pareto Frontier line */}
          {paretoPath && (
            <path
              d={paretoPath}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeDasharray="5 5"
              opacity="0.6"
            />
          )}

          {/* Data Points */}
          {visibleEntries.map((entry, idx) => {
            const cx = getX(entry.latency_p50_ms);
            const cy = getY(entry.accuracy);
            const color = getSeriesColor(entry.series, idx);
            const isHovered = hoveredEntry?.entry.series === entry.series;

            return (
              <g
                key={entry.series}
                className="chart-scatter-point"
                onMouseEnter={() => setHoveredEntry({ entry, x: cx, y: cy })}
                onMouseLeave={() => setHoveredEntry(null)}
              >
                {/* Glow ring on hover */}
                {isHovered && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={14}
                    fill={color}
                    opacity={0.25}
                  />
                )}
                {/* Point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 8 : 6}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={2}
                />

                {/* Offset Model Label for clarity */}
                <text
                  x={cx}
                  y={cy - 12}
                  textAnchor="middle"
                  style={{
                    fontSize: '11px',
                    fontWeight: isHovered ? 700 : 600,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                    pointerEvents: 'none',
                  }}
                >
                  {entry.model.replace('-q4km', '').replace('nemotron-', 'n-')} ({entry.accuracy_pct})
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Card */}
        {hoveredEntry && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hoveredEntry.x / width) * 100}%`,
              top: `${(hoveredEntry.y / height) * 100}%`,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: '4px' }}>
              {hoveredEntry.entry.medal} {hoveredEntry.entry.series}
            </div>
            <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#cbd5e1' }}>
              <span>Acc: <strong style={{ color: '#fff' }}>{hoveredEntry.entry.accuracy_pct}</strong></span>
              <span>p50: <strong style={{ color: '#fff' }}>{hoveredEntry.entry.latency_str}</strong></span>
              <span>Gap: <strong style={{ color: '#fff' }}>{hoveredEntry.entry.delta_str}</strong></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
