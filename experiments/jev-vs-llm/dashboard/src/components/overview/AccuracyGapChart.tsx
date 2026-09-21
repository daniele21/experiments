/**
 * AccuracyGapChart.tsx
 *
 * Premium horizontal bar chart comparing intent classification accuracy
 * across models. Features gradient-filled bars, animated entrance, glow
 * hover effects, and a leader highlight marker.
 */

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
  const rowHeight = 48;
  const marginTop = 30;
  const marginBottom = 50;
  const marginLeft = 240;
  const marginRight = 110;
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
          Evaluated intent classification accuracy. Compare the quality gap
          across model architectures and quantizations.
        </p>
      </div>

      <div className="chart-wrapper">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="interactive-chart"
          style={{ maxHeight: `${height}px` }}
        >
          {/* SVG Gradient definitions for premium bar fills */}
          <defs>
            {visibleEntries.map((entry, idx) => {
              const color = getSeriesColor(entry.series, idx);
              const gradId = `acc-bar-grad-${entry.series_id || idx}`;
              return (
                <linearGradient
                  key={gradId}
                  id={gradId}
                  x1="0%"
                  y1="0%"
                  x2="100%"
                  y2="0%"
                >
                  <stop offset="0%" stopColor={color} stopOpacity={0.85} />
                  <stop offset="100%" stopColor={color} stopOpacity={1} />
                </linearGradient>
              );
            })}
          </defs>

          {/* Vertical grid lines */}
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
                  y={height - marginBottom + 22}
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

          {/* X Axis title */}
          <text
            x={marginLeft + plotWidth / 2}
            y={height - 6}
            textAnchor="middle"
            className="chart-axis-title"
          >
            Intent Classification Accuracy
          </text>

          {/* Bars */}
          {visibleEntries.map((entry, idx) => {
            const y = marginTop + idx * rowHeight + 10;
            const barHeight = rowHeight - 20;
            const barWidth = entry.accuracy * plotWidth;
            const isHovered = hoveredIdx === idx;
            const color = getSeriesColor(entry.series, idx);
            const rowKey = entry.series_id || `${entry.series}_${entry.dataset || 'ds'}_${idx}`;
            const gradId = `acc-bar-grad-${entry.series_id || idx}`;

            return (
              <g
                key={rowKey}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Row background highlight on hover */}
                {isHovered && (
                  <rect
                    x={marginLeft - 8}
                    y={y - 4}
                    width={plotWidth + 100}
                    height={barHeight + 8}
                    rx={6}
                    fill="var(--surface-alt)"
                    opacity={0.65}
                  />
                )}

                {/* Model Label */}
                <text
                  x={marginLeft - 12}
                  y={y + barHeight / 2 + 4}
                  textAnchor="end"
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '12px',
                    fontWeight: isHovered ? 700 : 500,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                  }}
                >
                  {entry.series}
                </text>

                {/* Gradient bar with rounded corners */}
                <rect
                  x={marginLeft}
                  y={y}
                  width={Math.max(4, barWidth)}
                  height={barHeight}
                  rx={barHeight / 2}
                  fill={`url(#${gradId})`}
                  className="chart-bar-rect"
                  style={{
                    filter: isHovered ? `drop-shadow(0 0 8px ${color}88)` : undefined,
                    transition: 'filter 0.2s ease',
                  }}
                />

                {/* Accuracy % label at end of bar */}
                <text
                  x={marginLeft + barWidth + 10}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '13px',
                    fontWeight: 800,
                    fill: 'var(--text)',
                    letterSpacing: '-0.02em',
                  }}
                >
                  {entry.accuracy_pct}
                </text>

                {/* Delta label if not leader */}
                {entry.rank > 1 && (
                  <text
                    x={marginLeft + barWidth + 60}
                    y={y + barHeight / 2 + 4}
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      fill:
                        entry.delta_class === 'close'
                          ? 'var(--warning)'
                          : entry.delta_class === 'moderate'
                          ? '#ea580c'
                          : 'var(--danger)',
                      opacity: 0.85,
                    }}
                  >
                    ({entry.delta_str})
                  </text>
                )}

                {/* Leader crown indicator */}
                {entry.rank === 1 && (
                  <text
                    x={marginLeft + barWidth + 60}
                    y={y + barHeight / 2 + 5}
                    style={{ fontSize: '13px' }}
                  >
                    👑
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
