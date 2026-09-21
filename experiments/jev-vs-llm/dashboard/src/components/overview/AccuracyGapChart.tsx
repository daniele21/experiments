import React, { useState } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';

interface AccuracyGapChartProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
}

export const AccuracyGapChart: React.FC<AccuracyGapChartProps> = ({
  entries,
  selectedSeries,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const visibleEntries = entries.filter((e) => selectedSeries.has(e.series));
  if (visibleEntries.length === 0) {
    return null;
  }

  // Chart dimensions
  const rowHeight = 44;
  const marginTop = 30;
  const marginBottom = 40;
  const marginLeft = 240;
  const marginRight = 100;
  const width = 800;
  const height = marginTop + visibleEntries.length * rowHeight + marginBottom;
  const plotWidth = width - marginLeft - marginRight;

  // X scale: 0 to 1 (0% to 100%)
  const getX = (val: number) => marginLeft + val * plotWidth;

  const ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Accuracy Gap by Model</h3>
        <p className="chart-desc">
          Evaluated intent classification accuracy. Compare the quality gap across model architectures and quantizations.
        </p>
      </div>

      <div className="chart-wrapper">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="interactive-chart"
          style={{ maxHeight: `${height}px` }}
        >
          {/* Vertical Grid lines */}
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
                  {`${Math.round(t * 100)}%`}
                </text>
              </g>
            );
          })}

          {/* Left Y Axis line */}
          <line
            x1={marginLeft}
            y1={marginTop}
            x2={marginLeft}
            y2={height - marginBottom}
            className="chart-axis-line"
          />

          {/* Bars */}
          {visibleEntries.map((entry, idx) => {
            const y = marginTop + idx * rowHeight + 8;
            const barHeight = rowHeight - 16;
            const barWidth = entry.accuracy * plotWidth;
            const color = getSeriesColor(entry.series, idx);
            const isHovered = hoveredIdx === idx;

            return (
              <g
                key={entry.series}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
              >
                {/* Model Label */}
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

                {/* Bar */}
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

                {/* Accuracy % label at end of bar */}
                <text
                  x={marginLeft + barWidth + 8}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    fill: 'var(--text)',
                  }}
                >
                  {entry.accuracy_pct}
                </text>

                {/* Delta label if not leader */}
                {entry.rank > 1 && (
                  <text
                    x={marginLeft + barWidth + 58}
                    y={y + barHeight / 2 + 4}
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      fill: entry.delta_class === 'close' ? 'var(--warning)' : 'var(--danger)',
                    }}
                  >
                    ({entry.delta_str})
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
