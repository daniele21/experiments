import React, { useState } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';

interface LatencyComparisonChartProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
}

export const LatencyComparisonChart: React.FC<LatencyComparisonChartProps> = ({
  entries,
  selectedSeries,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  // Sort by latency ascending (fastest first)
  const sortedEntries = [...entries]
    .filter((e) => selectedSeries.has(e.series))
    .sort((a, b) => a.latency_p50_ms - b.latency_p50_ms);

  if (sortedEntries.length === 0) return null;

  const rowHeight = 44;
  const marginTop = 30;
  const marginBottom = 40;
  const marginLeft = 240;
  const marginRight = 120;
  const width = 800;
  const height = marginTop + sortedEntries.length * rowHeight + marginBottom;
  const plotWidth = width - marginLeft - marginRight;

  const maxLat = Math.max(9000, Math.ceil(Math.max(...sortedEntries.map((e) => e.latency_p50_ms)) / 1000) * 1000);
  const getX = (val: number) => marginLeft + (val / maxLat) * plotWidth;

  const ticks = [0, 2000, 4000, 6000, 8000];

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Latency Ranking (Fastest to Slowest)</h3>
        <p className="chart-desc">
          Median client-measured roundtrip latency per decision. Lower is better. Relative speed multipliers compare against the baseline.
        </p>
      </div>

      <div className="chart-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="interactive-chart">
          {ticks.map((t) => {
            const x = getX(t);
            return (
              <g key={t}>
                <line
                  x1={x}
                  y1={marginTop}
                  x2={x}
                  y2={height - marginBottom}
                  className="chart-grid-line"
                />
                <text
                  x={x}
                  y={height - marginBottom + 18}
                  textAnchor="middle"
                  className="chart-axis-text"
                >
                  {t === 0 ? '0' : `${t / 1000}s`}
                </text>
              </g>
            );
          })}

          <line
            x1={marginLeft}
            y1={marginTop}
            x2={marginLeft}
            y2={height - marginBottom}
            className="chart-axis-line"
          />

          {sortedEntries.map((entry, idx) => {
            const y = marginTop + idx * rowHeight + 8;
            const barHeight = rowHeight - 16;
            const barWidth = (entry.latency_p50_ms / maxLat) * plotWidth;
            const color = getSeriesColor(entry.series, idx);
            const isHovered = hoveredIdx === idx;

            return (
              <g
                key={entry.series}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                <text
                  x={marginLeft - 12}
                  y={y + barHeight / 2 + 4}
                  textAnchor="end"
                  className="chart-axis-text"
                  style={{
                    fontWeight: isHovered ? 700 : 500,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                  }}
                >
                  {entry.series}
                </text>

                <rect
                  x={marginLeft}
                  y={y}
                  width={Math.max(2, barWidth)}
                  height={barHeight}
                  rx={4}
                  fill={color}
                  className="chart-bar-rect"
                  opacity={isHovered ? 1 : 0.9}
                />

                <text
                  x={marginLeft + barWidth + 8}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    fill: 'var(--text)',
                  }}
                >
                  {entry.latency_str}
                </text>

                <text
                  x={marginLeft + barWidth + 68}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    fill: 'var(--accent)',
                  }}
                >
                  {entry.speed_str}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
