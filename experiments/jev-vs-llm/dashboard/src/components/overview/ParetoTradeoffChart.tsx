/**
 * ParetoTradeoffChart.tsx
 *
 * Flagship scatter plot visualizing the latency vs accuracy Pareto frontier.
 * High-performance UX/UI:
 *  - Logarithmic / Linear scale toggle to eliminate tight point clustering
 *  - Intelligent collision-avoidance label placement (zero overlapping text)
 *  - Label density modes: 'frontier' (clean default), 'all' (collision-free), 'hover' (minimalist)
 *  - Interactive coordinate crosshairs on hover
 *  - Selective focus with non-hovered point dimming
 *  - Glassmorphic hover tooltip with complete model statistics
 *  - Mathematically aligned Optimal Sweet Spot zone (<2s, >70%)
 */

import React, { useState, useMemo } from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import {
  getSeriesColor,
  formatCompactModelName,
  PARETO_CHART_CONFIG,
  BAR_GRADIENT_CONFIG,
} from '../../config/theme';
import { Zap, Target, TrendingUp } from 'lucide-react';

interface ParetoTradeoffChartProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
  isHeroView?: boolean;
}

interface PlacedLabel {
  text: string;
  x: number;
  y: number;
  textAnchor: 'middle' | 'start' | 'end';
  visible: boolean;
}

export const ParetoTradeoffChart: React.FC<ParetoTradeoffChartProps> = ({
  entries,
  selectedSeries,
}) => {
  const [scaleMode, setScaleMode] = useState<'log' | 'linear'>(PARETO_CHART_CONFIG.defaultScale);
  const [labelMode, setLabelMode] = useState<'frontier' | 'hover' | 'all'>(
    PARETO_CHART_CONFIG.defaultLabelMode
  );
  const [hoveredEntry, setHoveredEntry] = useState<{
    entry: LeaderboardEntry;
    x: number;
    y: number;
  } | null>(null);

  const visibleEntries = useMemo(
    () =>
      entries.filter(
        (e) => selectedSeries.has(e.series) || (e.series_id && selectedSeries.has(e.series_id))
      ),
    [entries, selectedSeries]
  );

  if (visibleEntries.length === 0) return null;

  // ── Canvas Dimensions ─────────────────────────────────────────────
  const width = 960;
  const height = 460;
  const marginTop = 45;
  const marginRight = 55;
  const marginBottom = 65;
  const marginLeft = 75;

  const plotWidth = width - marginLeft - marginRight;
  const plotHeight = height - marginTop - marginBottom;

  // ── Coordinate Scales ─────────────────────────────────────────────
  const latencies = visibleEntries.map((e) => e.latency_p50_ms);
  const maxLinearLat = Math.max(9000, Math.ceil(Math.max(...latencies) / 1000) * 1000);
  const maxAcc = 1.05; // headroom above 100%

  // Log scale: 100ms (10^2) to 10,000ms (10^4)
  const logMin = 2.0;
  const logMax = 4.0;

  const getX = (lat: number): number => {
    if (scaleMode === 'log') {
      const clamped = Math.max(100, Math.min(lat, 10000));
      const normalized = (Math.log10(clamped) - logMin) / (logMax - logMin);
      return marginLeft + normalized * plotWidth;
    }
    return marginLeft + (lat / maxLinearLat) * plotWidth;
  };

  const getY = (acc: number): number =>
    height - marginBottom - (acc / maxAcc) * plotHeight;

  // Ticks
  const xTicks =
    scaleMode === 'log'
      ? [100, 250, 500, 1000, 2000, 4000, 8000]
      : [0, 2000, 4000, 6000, 8000];

  const formatXTick = (t: number) => {
    if (scaleMode === 'log') {
      return t < 1000 ? `${t}ms` : `${t / 1000}s`;
    }
    return t === 0 ? '0' : `${t / 1000}s`;
  };

  const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

  // ── Pareto Frontier Calculation ──────────────────────────────────
  const sortedByLat = [...visibleEntries].sort((a, b) => a.latency_p50_ms - b.latency_p50_ms);
  const paretoPoints: LeaderboardEntry[] = [];
  let currentMaxAcc = -1;
  for (const entry of sortedByLat) {
    if (entry.accuracy > currentMaxAcc) {
      paretoPoints.push(entry);
      currentMaxAcc = entry.accuracy;
    }
  }

  const paretoSet = new Set(paretoPoints.map((p) => p.series_id || p.series));

  const paretoPath =
    paretoPoints.length > 1
      ? paretoPoints
          .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(p.latency_p50_ms)} ${getY(p.accuracy)}`)
          .join(' ')
      : '';

  // ── Optimal Zone Coordinates (<2s, >70%) ──────────────────────────
  const optX1 = marginLeft;
  const optX2 = getX(PARETO_CHART_CONFIG.optimalZone.maxLatencyMs);
  const optYTop = getY(1.0);
  const optYBottom = getY(PARETO_CHART_CONFIG.optimalZone.minAccuracy);

  // ── Intelligent Collision-Avoidance Label Engine ───────────────────
  const placedLabels: PlacedLabel[] = (() => {
    if (labelMode === 'hover') {
      return visibleEntries.map(() => ({
        text: '',
        x: 0,
        y: 0,
        textAnchor: 'middle',
        visible: false,
      }));
    }

    interface Box {
      x1: number;
      y1: number;
      x2: number;
      y2: number;
    }

    const occupiedBoxes: Box[] = [];
    const isColliding = (b1: Box, b2: Box) =>
      !(b1.x2 < b2.x1 || b1.x1 > b2.x2 || b1.y2 < b2.y1 || b1.y1 > b2.y2);

    // Prioritize Pareto frontier points and highest accuracy models
    const sortedEntriesWithIdx = visibleEntries
      .map((entry, idx) => ({ entry, idx }))
      .sort((a, b) => {
        const aPareto = paretoSet.has(a.entry.series_id || a.entry.series) ? 1 : 0;
        const bPareto = paretoSet.has(b.entry.series_id || b.entry.series) ? 1 : 0;
        if (aPareto !== bPareto) return bPareto - aPareto;
        return b.entry.accuracy - a.entry.accuracy;
      });

    const results: PlacedLabel[] = Array(visibleEntries.length);

    for (const { entry, idx } of sortedEntriesWithIdx) {
      const isPareto = paretoSet.has(entry.series_id || entry.series);

      // In frontier mode, only label points on the Pareto frontier
      if (labelMode === 'frontier' && !isPareto) {
        results[idx] = { text: '', x: 0, y: 0, textAnchor: 'middle', visible: false };
        continue;
      }

      const shortName = formatCompactModelName(entry.series);
      const text = `${shortName} · ${entry.accuracy_pct}`;
      const cx = getX(entry.latency_p50_ms);
      const cy = getY(entry.accuracy);

      const textWidth = text.length * 6.5;
      const textHeight = 16;

      // Candidate placement offsets: Above, Right, Left, Below
      const candidates: Array<{
        ox: number;
        oy: number;
        anchor: 'middle' | 'start' | 'end';
        box: Box;
      }> = [
        {
          ox: 0,
          oy: -14,
          anchor: 'middle',
          box: {
            x1: cx - textWidth / 2,
            y1: cy - 14 - textHeight,
            x2: cx + textWidth / 2,
            y2: cy - 14,
          },
        },
        {
          ox: 14,
          oy: 4,
          anchor: 'start',
          box: {
            x1: cx + 14,
            y1: cy + 4 - textHeight,
            x2: cx + 14 + textWidth,
            y2: cy + 4,
          },
        },
        {
          ox: -14,
          oy: 4,
          anchor: 'end',
          box: {
            x1: cx - 14 - textWidth,
            y1: cy + 4 - textHeight,
            x2: cx - 14,
            y2: cy + 4,
          },
        },
        {
          ox: 0,
          oy: 20,
          anchor: 'middle',
          box: {
            x1: cx - textWidth / 2,
            y1: cy + 20 - textHeight,
            x2: cx + textWidth / 2,
            y2: cy + 20,
          },
        },
      ];

      let placed = false;
      for (const cand of candidates) {
        // Must stay inside chart bounds
        if (
          cand.box.x1 < marginLeft ||
          cand.box.x2 > width - marginRight ||
          cand.box.y1 < marginTop ||
          cand.box.y2 > height - marginBottom
        ) {
          continue;
        }

        // Must not collide with existing placed labels
        const collision = occupiedBoxes.some((b) => isColliding(cand.box, b));
        if (!collision) {
          occupiedBoxes.push(cand.box);
          results[idx] = {
            text,
            x: cx + cand.ox,
            y: cy + cand.oy,
            textAnchor: cand.anchor,
            visible: true,
          };
          placed = true;
          break;
        }
      }

      if (!placed) {
        // Suppress label if it cannot be positioned without overlap
        results[idx] = { text, x: cx, y: cy - 14, textAnchor: 'middle', visible: false };
      }
    }

    return results;
  })();

  return (
    <div className="card frontier-flagship-card">
      {/* ── Card Header: Title & Interactive Controls ── */}
      <div className="card-header">
        <div className="card-title-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="frontier-icon-badge frontier-icon-speed">
              <Zap size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 className="card-title" style={{ margin: 0 }}>
                  Latency vs Accuracy Frontier
                </h3>
                <span className="frontier-badge-pulse speed-pulse">
                  <Target size={11} style={{ marginRight: '3px' }} />
                  Pareto Tradeoff
                </span>
              </div>
              <p className="card-subtitle" style={{ margin: '4px 0 0 0' }}>
                Identifies non-dominated models: architectures on the dashed line deliver the highest accuracy for their latency budget.
              </p>
            </div>
          </div>

          {/* Interactive UX Controls: Scale Mode & Label Mode */}
          <div className="frontier-controls-row">
            <div className="chart-control-group">
              <span className="control-label">Scale:</span>
              <div className="control-pill-group">
                <button
                  type="button"
                  className={`control-pill-btn ${scaleMode === 'log' ? 'active' : ''}`}
                  onClick={() => setScaleMode('log')}
                  title="Logarithmic scale evenly distributes models across fast sub-second and multi-second tiers"
                >
                  Log (Spread)
                </button>
                <button
                  type="button"
                  className={`control-pill-btn ${scaleMode === 'linear' ? 'active' : ''}`}
                  onClick={() => setScaleMode('linear')}
                  title="Linear scale shows raw millisecond distance"
                >
                  Linear
                </button>
              </div>
            </div>

            <div className="chart-control-group">
              <span className="control-label">Labels:</span>
              <div className="control-pill-group">
                <button
                  type="button"
                  className={`control-pill-btn ${labelMode === 'frontier' ? 'active' : ''}`}
                  onClick={() => setLabelMode('frontier')}
                  title="Show clean labels only for Pareto frontier leaders"
                >
                  Frontier only
                </button>
                <button
                  type="button"
                  className={`control-pill-btn ${labelMode === 'all' ? 'active' : ''}`}
                  onClick={() => setLabelMode('all')}
                  title="Show collision-free labels for all points"
                >
                  All (Smart)
                </button>
                <button
                  type="button"
                  className={`control-pill-btn ${labelMode === 'hover' ? 'active' : ''}`}
                  onClick={() => setLabelMode('hover')}
                  title="Minimalist view: labels show on hover only"
                >
                  Hover only
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="frontier-header-legend" style={{ marginTop: '12px' }}>
          <div className="legend-indicator-item">
            <span className="legend-dash-line" />
            <span>Pareto Frontier</span>
          </div>
          <div className="legend-indicator-item">
            <span className="legend-zone-swatch" />
            <span>Optimal Sweet Spot (&lt;2s &amp; &gt;70%)</span>
          </div>
          <div className="legend-indicator-item">
            <span
              style={{
                display: 'inline-block',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: BAR_GRADIENT_CONFIG.threeColor.middle,
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
            <span style={{ color: '#7c3aed' }}>Reasoning Mode (Think ON)</span>
          </div>
        </div>
      </div>

      {/* ── Chart Canvas ── */}
      <div style={{ position: 'relative', overflow: 'visible', padding: '4px 0' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          {/* SVG Definitions */}
          <defs>
            <linearGradient id="pareto-line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="50%" stopColor="#7c3aed" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="pareto-area-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.01} />
            </linearGradient>
            <radialGradient id="ideal-zone" cx="0%" cy="0%" r="100%">
              <stop offset="0%" stopColor="#059669" stopOpacity={0.12} />
              <stop offset="100%" stopColor="#059669" stopOpacity={0.02} />
            </radialGradient>
          </defs>

          {/* Optimal Sweet Spot Area (<2s, >70%) */}
          <rect
            x={optX1}
            y={optYTop}
            width={Math.max(20, optX2 - optX1)}
            height={Math.max(20, optYBottom - optYTop)}
            fill="url(#ideal-zone)"
            rx={8}
            stroke="#059669"
            strokeWidth={1.2}
            strokeDasharray="4 4"
            opacity={0.6}
          />
          <text
            x={optX1 + 10}
            y={optYTop + 16}
            fill="#059669"
            style={{
              fontSize: '11px',
              fontWeight: 700,
              fontFamily: 'var(--font-sans)',
              letterSpacing: '0.02em',
            }}
          >
            🎯 Optimal Sweet Spot (&lt;2s &amp; &gt;70%)
          </text>

          {/* Horizontal Grid lines (Accuracy) */}
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

          {/* Vertical Grid lines (Latency) */}
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
                  {formatXTick(t)}
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
            y={height - 12}
            textAnchor="middle"
            className="chart-axis-title"
            style={{ fontWeight: 700, letterSpacing: '0.04em' }}
          >
            {scaleMode === 'log'
              ? 'Median Latency (Log Scale — Spaced for Clarity)'
              : 'Median Latency (Linear Scale)'}
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

          {/* Shaded Area Under Pareto Curve */}
          {paretoPoints.length > 1 && (
            <path
              d={`${paretoPath} L ${getX(
                paretoPoints[paretoPoints.length - 1].latency_p50_ms
              )} ${height - marginBottom} L ${getX(
                paretoPoints[0].latency_p50_ms
              )} ${height - marginBottom} Z`}
              fill="url(#pareto-area-grad)"
            />
          )}

          {/* Dashed Pareto Frontier Curve */}
          {paretoPath && (
            <path
              d={paretoPath}
              fill="none"
              stroke="url(#pareto-line-grad)"
              strokeWidth="3"
              strokeDasharray="6 4"
              opacity={0.88}
              style={{ filter: 'drop-shadow(0 2px 4px rgba(79, 70, 229, 0.3))' }}
            />
          )}

          {/* Hover Crosshairs */}
          {hoveredEntry && (
            <g style={{ pointerEvents: 'none' }}>
              <line
                x1={hoveredEntry.x}
                y1={marginTop}
                x2={hoveredEntry.x}
                y2={height - marginBottom}
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                opacity={0.6}
              />
              <line
                x1={marginLeft}
                y1={hoveredEntry.y}
                x2={width - marginRight}
                y2={hoveredEntry.y}
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                opacity={0.6}
              />
            </g>
          )}

          {/* Scatter Data Points & Clean Labels */}
          {visibleEntries.map((entry, idx) => {
            const color = getSeriesColor(entry.series, idx);
            const cx = getX(entry.latency_p50_ms);
            const cy = getY(entry.accuracy);
            const entryId = entry.series_id || entry.series;
            const isHovered =
              (hoveredEntry?.entry.series_id || hoveredEntry?.entry.series) === entryId;
            const isAnyHovered = hoveredEntry !== null;
            const isThinking =
              entry.thinking_mode === 'on' || entry.series.toLowerCase().includes('thinking');
            const isPareto = paretoSet.has(entryId);
            const labelInfo = placedLabels[idx];

            return (
              <g
                key={entryId}
                onMouseEnter={() => setHoveredEntry({ entry, x: cx, y: cy })}
                onMouseLeave={() => setHoveredEntry(null)}
                style={{
                  cursor: 'pointer',
                  opacity: isAnyHovered && !isHovered ? 0.25 : 1,
                  transition: 'opacity 0.2s ease',
                }}
              >
                {/* Hover Pulse Ring */}
                {isHovered && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={24}
                    fill={isThinking ? '#a855f7' : color}
                    opacity={0.22}
                  />
                )}

                {/* Reasoning / Thinking Concentric Dashed Ring */}
                {isThinking && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 14 : 11}
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

                {/* Pareto Frontier Leader Ring */}
                {isPareto && !isThinking && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 13 : 9}
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth={1.5}
                    opacity={0.7}
                  />
                )}

                {/* Main Scatter Point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 9 : isPareto ? 7 : 6}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={2.5}
                  style={{
                    filter: isHovered
                      ? `drop-shadow(0 0 10px ${color})`
                      : isPareto
                      ? 'drop-shadow(0 2px 5px rgba(99, 102, 241, 0.4))'
                      : 'drop-shadow(0 1px 3px rgba(0,0,0,0.15))',
                    transition: 'r 0.15s ease, filter 0.15s ease',
                  }}
                />

                {/* Clean, Non-colliding Label (or on hover) */}
                {(labelInfo?.visible || isHovered) && (
                  <text
                    x={isHovered ? cx : labelInfo.x}
                    y={isHovered ? cy - 16 : labelInfo.y}
                    textAnchor={isHovered ? 'middle' : labelInfo.textAnchor}
                    style={{
                      fontSize: isHovered ? '12px' : '11px',
                      fontWeight: isHovered ? 800 : isPareto ? 700 : 600,
                      fill: isHovered
                        ? 'var(--text)'
                        : isPareto
                        ? '#4f46e5'
                        : 'var(--text-muted)',
                      pointerEvents: 'none',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {isHovered
                      ? `${formatCompactModelName(entry.series)} · ${entry.accuracy_pct}`
                      : labelInfo.text}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Glassmorphic Interactive Tooltip */}
        {hoveredEntry && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(hoveredEntry.x / width) * 100}%`,
              top: `${(hoveredEntry.y / height) * 100}%`,
              transform: 'translate(-50%, -125%)',
              pointerEvents: 'none',
              zIndex: 20,
            }}
          >
            <div
              style={{
                fontWeight: 800,
                fontSize: '13px',
                marginBottom: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
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

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '8px',
                fontSize: '11px',
                marginTop: '6px',
              }}
            >
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
                <strong style={{ color: '#a7f3d0' }}>
                  {hoveredEntry.entry.dataset_label ||
                    (hoveredEntry.entry.dataset === 'public' ? 'Banking77' : 'Smoke')}
                </strong>
              </div>
              <div>
                <span style={{ color: '#94a3b8' }}>Rank: </span>
                <strong style={{ color: '#fbbf24' }}>#{hoveredEntry.entry.rank}</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Strategic Takeaway Callout */}
      <div className="frontier-card-footer">
        <div className="frontier-insight-pill">
          <span className="insight-badge">
            <TrendingUp size={12} style={{ marginRight: '4px' }} />
            Strategic Verdict
          </span>
          <span className="insight-text">
            <strong>Jev (261ms / 72.7%)</strong> and <strong>GPT-5.6 Luna (1427ms / 79.2%)</strong> define the upper-left Pareto boundaries.
            For on-device local execution, <strong>Qwen 9B (62.3%)</strong> and <strong>Nemotron Nano 4B</strong> achieve the strongest balance between memory and accuracy.
          </span>
        </div>
      </div>
    </div>
  );
};
