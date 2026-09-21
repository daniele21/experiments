/**
 * ParetoTradeoffChart.tsx
 *
 * Flagship scatter plot visualizing the latency vs accuracy Pareto frontier.
 * Features:
 *  - 960x460 high-resolution canvas with generous breathing room
 *  - Uncluttered, collision-free label positioning
 *  - Prominent flagship hero header with status badges and legend
 *  - Glowing Pareto dominance frontier curve with shaded area
 *  - Glassmorphic hover tooltip with complete model statistics
 *  - Actionable strategic takeaway footer
 */

import React, { useState } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';
import { Zap, Target, TrendingUp } from 'lucide-react';

interface ParetoTradeoffChartProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
  isHeroView?: boolean;
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

  const visibleEntries = entries.filter((e) =>
    selectedSeries.has(e.series) || (e.series_id && selectedSeries.has(e.series_id))
  );
  if (visibleEntries.length === 0) return null;

  // ── Chart dimensions ─────────────────────────────────────────────
  const width = 960;
  const height = 460;
  const marginTop = 40;
  const marginRight = 55;
  const marginBottom = 65;
  const marginLeft = 75;

  const plotWidth = width - marginLeft - marginRight;
  const plotHeight = height - marginTop - marginBottom;

  // ── Domain ───────────────────────────────────────────────────────
  const latencies = visibleEntries.map((e) => e.latency_p50_ms);
  const maxLat = Math.max(9000, Math.ceil(Math.max(...latencies) / 1000) * 1000);
  const maxAcc = 1.05; // 0% to 100% with headroom so top points never touch the header

  const getX = (lat: number) => marginLeft + (lat / maxLat) * plotWidth;
  const getY = (acc: number) => height - marginBottom - (acc / maxAcc) * plotHeight;

  // ── Pareto Frontier points (sorted by latency ascending, filter strictly increasing accuracy)
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
  const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

  // ── Clean Collision-free Label Offsets ─────────────────────────────
  const labelOffsets = visibleEntries.map((entry, i) => {
    const cx = getX(entry.latency_p50_ms);
    const cy = getY(entry.accuracy);
    let offsetY = -14;
    let offsetX = 0;
    let textAnchor: 'middle' | 'start' | 'end' = 'middle';

    // Near top edge: place below
    if (cy < marginTop + 35) {
      offsetY = 20;
    }
    // Near right edge: anchor end
    if (cx > width - marginRight - 120) {
      textAnchor = 'end';
      offsetX = -12;
    }
    // Near left edge: anchor start
    if (cx < marginLeft + 100) {
      textAnchor = 'start';
      offsetX = 12;
    }

    // Pairwise collision repulsion
    for (let j = 0; j < visibleEntries.length; j++) {
      if (i === j) continue;
      const other = visibleEntries[j];
      const ocx = getX(other.latency_p50_ms);
      const ocy = getY(other.accuracy);
      const dx = Math.abs(cx - ocx);
      const dy = Math.abs(cy - ocy);

      if (dx < 90 && dy < 38) {
        if (cy >= ocy) {
          offsetY = 22;
          offsetX = cx >= ocx ? 12 : -12;
        } else {
          offsetY = -16;
          offsetX = cx >= ocx ? 12 : -12;
        }
        break;
      }
    }
    return { offsetY, offsetX, textAnchor };
  });

  return (
    <div className="card frontier-flagship-card">
      <div className="card-header">
        <div className="card-title-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="frontier-icon-badge frontier-icon-speed">
              <Zap size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 className="card-title" style={{ margin: 0 }}>Latency vs Accuracy Frontier</h3>
                <span className="frontier-badge-pulse speed-pulse">
                  <Target size={11} style={{ marginRight: '3px' }} />
                  Primary Strategic Pareto Framework
                </span>
              </div>
              <p className="card-subtitle" style={{ margin: '4px 0 0 0' }}>
                Identifies non-dominated architectures: models on the dashed line deliver the highest intent accuracy for their speed tier.
              </p>
            </div>
          </div>

          <div className="frontier-header-legend">
            <div className="legend-indicator-item">
              <span className="legend-dash-line" />
              <span>Pareto Frontier</span>
            </div>
            <div className="legend-indicator-item">
              <span className="legend-zone-swatch" />
              <span>Optimal Zone (&lt;3s &amp; &gt;70%)</span>
            </div>
            <div className="legend-indicator-item">
              <span
                style={{
                  display: 'inline-block',
                  width: '9px',
                  height: '9px',
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  border: '1.5px solid #fff',
                  boxShadow: '0 0 2px rgba(0,0,0,0.3)',
                }}
              />
              <span>Direct Inference</span>
            </div>
            <div className="legend-indicator-item">
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '15px',
                  height: '15px',
                  borderRadius: '50%',
                  border: '1.5px dashed #a855f7',
                  background: 'rgba(168, 85, 247, 0.12)',
                  fontSize: '9px',
                  lineHeight: 1,
                }}
              >
                🧠
              </span>
              <span style={{ color: '#7c3aed' }}>Reasoning (Thinking ON)</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{ position: 'relative', overflow: 'visible', padding: '8px 0' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          {/* SVG Defs: glow filter and gradient line */}
          <defs>
            <linearGradient id="pareto-line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="pareto-area-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.01" />
            </linearGradient>
            <radialGradient id="ideal-zone" cx="0%" cy="0%" r="100%">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.10" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.01" />
            </radialGradient>
          </defs>

          {/* Ideal Tradeoff Zone (top-left subtle highlight with dashed perimeter) */}
          <rect
            x={marginLeft}
            y={marginTop}
            width={plotWidth * 0.35}
            height={plotHeight * 0.35}
            fill="url(#ideal-zone)"
            rx={8}
            stroke="#059669"
            strokeWidth={1}
            strokeDasharray="4 4"
            opacity={0.4}
          />

          {/* Horizontal Grid lines */}
          {yTicks.map((acc) => {
            const y = getY(acc);
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

          {/* Vertical Grid lines */}
          {xTicks.map((t) => {
            const x = getX(t);
            return (
              <g key={`x-${t}`}>
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
                  {t === 0 ? '0' : `${t / 1000}s`}
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

          {/* Bottom X Axis */}
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
            Median Roundtrip Latency (milliseconds / seconds)
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

          {/* Pareto Frontier – shaded area under curve */}
          {paretoPoints.length > 1 && (
            <path
              d={`${paretoPath} L ${getX(paretoPoints[paretoPoints.length - 1].latency_p50_ms)} ${height - marginBottom} L ${getX(paretoPoints[0].latency_p50_ms)} ${height - marginBottom} Z`}
              fill="url(#pareto-area-grad)"
            />
          )}

          {/* Pareto Frontier – gradient dashed line */}
          {paretoPath && (
            <path
              d={paretoPath}
              fill="none"
              stroke="url(#pareto-line-grad)"
              strokeWidth="3"
              strokeDasharray="6 4"
              opacity={0.85}
              style={{ filter: 'drop-shadow(0 2px 4px rgba(79, 70, 229, 0.3))' }}
            />
          )}

          {/* Data points */}
          {visibleEntries.map((entry, idx) => {
            const color = getSeriesColor(entry.series, idx);
            const cx = getX(entry.latency_p50_ms);
            const cy = getY(entry.accuracy);
            const entryId = entry.series_id || entry.series;
            const isHovered = (hoveredEntry?.entry.series_id || hoveredEntry?.entry.series) === entryId;
            const isThinking = entry.thinking_mode === 'on' || entry.series.toLowerCase().includes('thinking');
            const isSmoke = entry.dataset === 'smoke' || entry.series.toLowerCase().includes('smoke');

            const { offsetY, offsetX, textAnchor } = labelOffsets[idx] || {
              offsetY: -14,
              offsetX: 0,
              textAnchor: 'middle',
            };

            const cleanName = entry.model
              .replace('-q4km', '')
              .replace('nemotron-', 'n-');

            let labelSuffix = '';
            if (isThinking && isSmoke) {
              labelSuffix = ' 🧠 [Think·Smoke]';
            } else if (isThinking) {
              labelSuffix = ' 🧠 [Think]';
            } else if (isSmoke) {
              labelSuffix = ' [Smoke]';
            }

            const modelLabel = `${cleanName}${labelSuffix} (${entry.accuracy_pct})`;

            return (
              <g
                key={entryId}
                onMouseEnter={() => setHoveredEntry({ entry, x: cx, y: cy })}
                onMouseLeave={() => setHoveredEntry(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Outer halo ring on hover */}
                {isHovered && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={24}
                    fill={isThinking ? '#a855f7' : color}
                    opacity={0.2}
                  />
                )}

                {/* Thinking Mode Outer Dashed Concentric Ring */}
                {isThinking && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 13 : 10.5}
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth={2}
                    strokeDasharray="3 2"
                    style={{
                      filter: 'drop-shadow(0 0 5px rgba(168, 85, 247, 0.6))',
                      transition: 'all 0.15s ease',
                    }}
                  />
                )}

                {/* Main point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 9 : 6.5}
                  fill={color}
                  stroke={isThinking ? '#7c3aed' : '#ffffff'}
                  strokeWidth={isThinking ? 2 : 2.5}
                  style={{
                    filter: isHovered
                      ? `drop-shadow(0 0 10px ${color})`
                      : isThinking
                      ? 'drop-shadow(0 2px 6px rgba(168, 85, 247, 0.4))'
                      : 'drop-shadow(0 1px 3px rgba(0,0,0,0.2))',
                    transition: 'r 0.15s ease, filter 0.15s ease',
                  }}
                />

                {/* Model label */}
                <text
                  x={cx + offsetX}
                  y={cy + offsetY}
                  textAnchor={textAnchor}
                  style={{
                    fontSize: isHovered ? '12px' : '11px',
                    fontWeight: isHovered ? 800 : isThinking ? 700 : 600,
                    fill: isHovered
                      ? 'var(--text)'
                      : isThinking
                      ? '#6d28d9'
                      : 'var(--text-muted)',
                    pointerEvents: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {modelLabel}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Glassmorphism Tooltip */}
        {hoveredEntry && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hoveredEntry.x / width) * 100}%`,
              top: `${(hoveredEntry.y / height) * 100}%`,
              transform: 'translate(-50%, -120%)',
              pointerEvents: 'none',
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 800, fontSize: '13px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>{hoveredEntry.entry.medal}</span>
              <span>{hoveredEntry.entry.series}</span>
            </div>
            {hoveredEntry.entry.thinking_mode === 'on' && (
              <div style={{ marginBottom: '6px' }}>
                <span
                  style={{
                    background: 'rgba(168, 85, 247, 0.25)',
                    color: '#d8b4fe',
                    border: '1px solid rgba(168, 85, 247, 0.5)',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 800,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  🧠 REASONING (THINKING ACTIVE)
                </span>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '11px', marginTop: '6px' }}>
              <div>
                <span style={{ color: '#94a3b8' }}>Accuracy: </span>
                <strong style={{ color: '#ffffff' }}>{hoveredEntry.entry.accuracy_pct}</strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Latency p50: </span>
                <strong style={{ color: '#38bdf8' }}>{hoveredEntry.entry.latency_str}</strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Dataset: </span>
                <strong style={{ color: '#a7f3d0' }}>{hoveredEntry.entry.dataset_label || (hoveredEntry.entry.dataset === 'public' ? 'Banking77' : 'Smoke')}</strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Thinking: </span>
                <strong style={{ color: hoveredEntry.entry.thinking_mode === 'on' ? '#c084fc' : '#e2e8f0' }}>
                  {hoveredEntry.entry.thinking_mode === 'on' ? 'ON (Reasoning)' : 'Direct'}
                </strong>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Flagship Strategic Takeaway Callout */}
      <div className="frontier-card-footer">
        <div className="frontier-insight-pill">
          <span className="insight-badge">
            <TrendingUp size={12} style={{ marginRight: '4px' }} />
            Strategic Verdict
          </span>
          <span className="insight-text">
            <strong>Jev (261ms / 100% Smoke · 275ms / 72.7% Public)</strong> and <strong>GPT-5.6 Luna (1427ms / 79.2%)</strong> define the upper-left Pareto boundaries.
            For zero-cost on-device execution, <strong>Nemotron Nano 4B Q4</strong> establishes the local sweet spot, jumping from <strong>83.3% to 87.5%</strong> when reasoning traces are active.
          </span>
        </div>
      </div>
    </div>
  );
};
