/**
 * LatencyComparisonChart.tsx
 *
 * Premium horizontal bar chart ranking models by median p50 latency
 * (fastest first). Features gradient bars, staggered animation,
 * hover glow, and speed multiplier badges.
 */

import React, { useState } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { THEME, BAR_GRADIENT_CONFIG } from '../../config/theme';

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

  const rowHeight = 48;
  const marginTop = 30;
  const marginBottom = 50;
  const marginLeft = 240;
  const marginRight = 130;
  const width = 800;
  const height = marginTop + sortedEntries.length * rowHeight + marginBottom;
  const plotWidth = width - marginLeft - marginRight;

  const maxLat = Math.max(
    9000,
    Math.ceil(Math.max(...sortedEntries.map((e) => e.latency_p50_ms)) / 1000) * 1000
  );
  const getX = (val: number) => marginLeft + (val / maxLat) * plotWidth;

  const ticks = [0, 2000, 4000, 6000, 8000];

  // Vertical bounds for cross-bar vertical gradient (from top of first bar to bottom of last bar)
  const barHeight = rowHeight - 20;
  const barY1 = marginTop + 10;
  const barY2 =
    sortedEntries.length > 1
      ? marginTop + (sortedEntries.length - 1) * rowHeight + 10 + barHeight
      : barY1 + barHeight;

  return (
    <div className="chart-card">
      <div className="chart-header">
        <h3 className="chart-title">Latency Ranking (Fastest → Slowest)</h3>
        <p className="chart-desc">
          Median client-measured roundtrip latency per decision. Lower is
          better. Speed multipliers compare against the slowest baseline.
        </p>
      </div>

      <div className="chart-wrapper">
        <svg viewBox={`0 0 ${width} ${height}`} className="interactive-chart">
          {/* SVG Gradient defs */}
          <defs>
            {/* Unified 2 or 3 Color Gradient applied vertically across all latency bars */}
            <linearGradient
              id="lat-bar-unified-grad"
              gradientUnits={
                BAR_GRADIENT_CONFIG.direction === 'vertical'
                  ? 'userSpaceOnUse'
                  : 'objectBoundingBox'
              }
              x1="0"
              y1={BAR_GRADIENT_CONFIG.direction === 'vertical' ? barY1 : '0%'}
              x2={BAR_GRADIENT_CONFIG.direction === 'vertical' ? '0' : '100%'}
              y2={BAR_GRADIENT_CONFIG.direction === 'vertical' ? barY2 : '0%'}
            >
              <stop
                offset="0%"
                stopColor={
                  BAR_GRADIENT_CONFIG.mode === 'three-color'
                    ? BAR_GRADIENT_CONFIG.threeColor.start
                    : BAR_GRADIENT_CONFIG.twoColor.start
                }
                stopOpacity={0.92}
              />
              {BAR_GRADIENT_CONFIG.mode === 'three-color' && (
                <stop
                  offset="50%"
                  stopColor={BAR_GRADIENT_CONFIG.threeColor.middle}
                  stopOpacity={0.95}
                />
              )}
              <stop
                offset="100%"
                stopColor={
                  BAR_GRADIENT_CONFIG.mode === 'three-color'
                    ? BAR_GRADIENT_CONFIG.threeColor.end
                    : BAR_GRADIENT_CONFIG.twoColor.end
                }
                stopOpacity={1}
              />
            </linearGradient>

            {/* Dedicated Hover Highlight Gradient (configurable in theme.ts) */}
            <linearGradient
              id="lat-bar-grad-hover"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor={THEME.chart.barHover.startColor} stopOpacity={1} />
              <stop offset="100%" stopColor={THEME.chart.barHover.endColor} stopOpacity={1} />
            </linearGradient>
          </defs>

          {/* Grid lines */}
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
                  {`${t} ms`}
                </text>
              </g>
            );
          })}

          {/* Left Y Axis */}
          <line
            x1={marginLeft}
            y1={marginTop}
            x2={marginLeft}
            y2={height - marginBottom}
            className="chart-axis-line"
          />

          {/* X Axis label */}
          <text
            x={marginLeft + plotWidth / 2}
            y={height - 6}
            textAnchor="middle"
            className="chart-axis-title"
          >
            Median Latency (ms, lower is better)
          </text>

          {/* Bars */}
          {sortedEntries.map((entry, idx) => {
            const y = marginTop + idx * rowHeight + 10;
            const barHeight = rowHeight - 20;
            const barWidth = (entry.latency_p50_ms / maxLat) * plotWidth;
            const isHovered = hoveredIdx === idx;
            const rowKey = entry.series_id || `${entry.series}_${entry.dataset || 'ds'}_${idx}`;

            return (
              <g
                key={rowKey}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Row hover highlight */}
                {isHovered && (
                  <rect
                    x={marginLeft - 8}
                    y={y - 4}
                    width={plotWidth + 120}
                    height={barHeight + 8}
                    rx={6}
                    fill="var(--surface-alt)"
                    opacity={0.65}
                  />
                )}

                {/* Model label */}
                <text
                  x={marginLeft - 12}
                  y={y + barHeight / 2 + 4}
                  textAnchor="end"
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '12px',
                    fontWeight: isHovered ? 700 : 500,
                    fill: isHovered ? 'var(--text)' : 'var(--text-muted)',
                    transition: 'fill 0.2s ease, font-weight 0.2s ease',
                  }}
                >
                  {entry.series}
                </text>

                {/* Gradient bar with distinct hover highlight */}
                <rect
                  x={marginLeft}
                  y={y}
                  width={Math.max(4, barWidth)}
                  height={barHeight}
                  rx={barHeight / 2}
                  fill={isHovered ? 'url(#lat-bar-grad-hover)' : 'url(#lat-bar-unified-grad)'}
                  stroke={isHovered ? THEME.chart.barHover.stroke : 'none'}
                  strokeWidth={isHovered ? THEME.chart.barHover.strokeWidth : 0}
                  className={`chart-bar-rect ${isHovered ? 'is-hovered' : ''}`}
                  onMouseEnter={() => setHoveredIdx(idx)}
                  onMouseLeave={() => setHoveredIdx(null)}
                  style={{
                    filter: isHovered
                      ? THEME.chart.barHover.dropShadow
                      : idx === 0
                      ? 'drop-shadow(0 2px 8px rgba(6, 182, 212, 0.35))'
                      : undefined,
                    opacity: hoveredIdx !== null && !isHovered ? THEME.chart.barHover.dimmedOpacity : 1,
                    transition: 'fill 0.2s ease, filter 0.2s ease, opacity 0.2s ease',
                  }}
                />

                {/* Latency value */}
                <text
                  x={marginLeft + barWidth + 10}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '13px',
                    fontWeight: isHovered ? 900 : 800,
                    fill: isHovered ? THEME.chart.barHover.stroke : 'var(--text)',
                    letterSpacing: '-0.02em',
                    transition: 'fill 0.2s ease',
                  }}
                >
                  {entry.latency_str}
                </text>

                {/* Speed multiplier badge */}
                <text
                  x={marginLeft + barWidth + 76}
                  y={y + barHeight / 2 + 4}
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    fill: entry.speed_class === 'fastest' ? 'var(--success)' : 'var(--accent)',
                    opacity: 0.9,
                  }}
                >
                  {entry.speed_str}
                </text>

                {/* Fastest bolt indicator */}
                {idx === 0 && (
                  <text
                    x={marginLeft + barWidth + 10 + entry.latency_str.length * 7 + 50 + entry.speed_str.length * 6 + 12}
                    y={y + barHeight / 2 + 5}
                    style={{ fontSize: '13px' }}
                  >
                    ⚡
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
