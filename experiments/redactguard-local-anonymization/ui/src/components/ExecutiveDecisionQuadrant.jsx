/**
 * ExecutiveDecisionQuadrant.jsx
 *
 * Visual 2x2 Decision Matrix mapping models across Privacy Protection (Y-axis)
 * vs Operational Reliability (X-axis). Fully supports Light and Dark modes using
 * CSS theme variables and smart label anchoring to prevent edge clipping.
 */

import { useState } from "react";
import { formatMs, formatPercent } from "../utils/formatters";

export function ExecutiveDecisionQuadrant({
  models = [],
  recommendedModel,
  onSelectModel,
  selectedModel,
}) {
  const [hoveredModel, setHoveredModel] = useState(null);

  // SVG dimensions
  const width = 680;
  const height = 410;
  const padding = { top: 40, right: 65, bottom: 50, left: 65 };

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // Thresholds for dividing the quadrants (e.g., 80% reliability, 80% privacy)
  const thresholdX = 0.8;
  const thresholdY = 0.8;

  const splitX = padding.left + plotWidth * thresholdX;
  const splitY = padding.top + plotHeight * (1 - thresholdY);

  return (
    <div className="executive-quadrant-container">
      <div className="executive-quadrant-header">
        <div>
          <span className="kicker">Matrice di Posizionamento</span>
          <h3>Privacy vs Affidabilità Operativa</h3>
        </div>
        <div className="executive-quadrant-legend">
          <span className="legend-item legend-item--production">
            <i /> Idoneo alla Produzione
          </span>
          <span className="legend-item legend-item--risk">
            <i /> Rischio Operativo / Timeout
          </span>
        </div>
      </div>

      <div className="executive-quadrant-canvas-wrapper">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="executive-quadrant-svg"
          aria-label="Matrice 2x2 Privacy vs Affidabilità"
        >
          {/* Quadrant Background Zones using theme variables */}
          {/* Top-Right: Production Ready (High Privacy, High Reliability) */}
          <rect
            x={splitX}
            y={padding.top}
            width={plotWidth * (1 - thresholdX)}
            height={plotHeight * thresholdY}
            fill="var(--quadrant-bg-production)"
            stroke="var(--quadrant-border-production)"
            strokeWidth="1"
            rx="6"
          />
          <text
            x={width - padding.right - 12}
            y={padding.top + 22}
            textAnchor="end"
            className="quadrant-zone-label quadrant-zone-label--positive"
          >
            ✓ IDONEO ALLA PRODUZIONE
          </text>

          {/* Top-Left: High Privacy, Unstable / Operational Risk */}
          <rect
            x={padding.left}
            y={padding.top}
            width={plotWidth * thresholdX}
            height={plotHeight * thresholdY}
            fill="var(--quadrant-bg-unstable)"
            stroke="var(--quadrant-border-unstable)"
            strokeWidth="1"
            rx="6"
          />
          <text
            x={padding.left + 12}
            y={padding.top + 22}
            className="quadrant-zone-label quadrant-zone-label--warning"
          >
            ALTA PRIVACY / RISCHIO ESECUZIONE
          </text>

          {/* Bottom-Right: Fast / Reliable, but Low Privacy */}
          <rect
            x={splitX}
            y={splitY}
            width={plotWidth * (1 - thresholdX)}
            height={plotHeight * (1 - thresholdY)}
            fill="var(--quadrant-bg-neutral)"
            stroke="var(--quadrant-border-neutral)"
            strokeWidth="1"
            rx="6"
          />
          <text
            x={width - padding.right - 12}
            y={splitY + 22}
            textAnchor="end"
            className="quadrant-zone-label quadrant-zone-label--neutral"
          >
            BASSA PROTEZIONE PII
          </text>

          {/* Bottom-Left: Non-compliant / Unstable */}
          <rect
            x={padding.left}
            y={splitY}
            width={plotWidth * thresholdX}
            height={plotHeight * (1 - thresholdY)}
            fill="var(--quadrant-bg-risk)"
            stroke="var(--quadrant-border-risk)"
            strokeWidth="1"
            rx="6"
          />
          <text
            x={padding.left + 12}
            y={splitY + 22}
            className="quadrant-zone-label quadrant-zone-label--risk"
          >
            NON CONFORME / RISCHIO CRITICO
          </text>

          {/* Dividing Threshold Lines */}
          <line
            x1={splitX}
            y1={padding.top}
            x2={splitX}
            y2={height - padding.bottom}
            stroke="var(--quadrant-grid-color)"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
          <line
            x1={padding.left}
            y1={splitY}
            x2={width - padding.right}
            y2={splitY}
            stroke="var(--quadrant-grid-color)"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />

          {/* Axis Labels */}
          <text
            x={padding.left + plotWidth / 2}
            y={height - 12}
            textAnchor="middle"
            className="quadrant-axis-label"
          >
            Affidabilità Operativa (Tasso di Inferenza con Successo) →
          </text>
          <text
            x={-(padding.top + plotHeight / 2)}
            y={18}
            textAnchor="middle"
            transform="rotate(-90)"
            className="quadrant-axis-label"
          >
            Copertura Privacy (PII Recall %) →
          </text>

          {/* Axis Tick Marks & Labels */}
          {/* X: 0%, 50%, 80%, 100% */}
          {[0, 0.5, 0.8, 1].map((val) => {
            const x = padding.left + plotWidth * val;
            return (
              <g key={`xtick-${val}`}>
                <line
                  x1={x}
                  y1={height - padding.bottom}
                  x2={x}
                  y2={height - padding.bottom + 5}
                  stroke="var(--quadrant-grid-color)"
                />
                <text
                  x={x}
                  y={height - padding.bottom + 18}
                  textAnchor="middle"
                  className="quadrant-tick"
                >
                  {Math.round(val * 100)}%
                </text>
              </g>
            );
          })}

          {/* Y: 50%, 80%, 100% (skip 0% to avoid collision with X-axis 0% tick) */}
          {[0.5, 0.8, 1].map((val) => {
            const y = padding.top + plotHeight * (1 - val);
            return (
              <g key={`ytick-${val}`}>
                <line
                  x1={padding.left - 5}
                  y1={y}
                  x2={padding.left}
                  y2={y}
                  stroke="var(--quadrant-grid-color)"
                />
                <text
                  x={padding.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  className="quadrant-tick"
                >
                  {Math.round(val * 100)}%
                </text>
              </g>
            );
          })}

          {/* Render Model Dots */}
          {models.map((item) => {
            const cx = padding.left + plotWidth * Math.max(0, Math.min(1, item.successRate));
            const cy = padding.top + plotHeight * (1 - Math.max(0, Math.min(1, item.recall)));

            const isRecommended = item.model === recommendedModel?.model;
            const isSelected = item.model === selectedModel;
            const isHovered = item.model === hoveredModel?.model;

            const circleColor = isRecommended
              ? "#10b981" // Emerald
              : item.isReliable && item.recall >= 0.8
                ? "#3b82f6" // Blue
                : item.isQuarantined
                  ? "#ef4444" // Red
                  : "#f59e0b"; // Amber

            // Smart label positioning to prevent clipping off SVG boundaries
            let labelAnchor = "middle";
            let labelX = cx;
            let labelY = cy - 16;

            if (cx > width - padding.right - 70) {
              labelAnchor = "end";
              labelX = cx - 14;
              labelY = cy + 4;
            } else if (cx < padding.left + 70) {
              labelAnchor = "start";
              labelX = cx + 14;
              labelY = cy + 4;
            }

            return (
              <g
                key={item.model}
                className="quadrant-model-point"
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredModel(item)}
                onMouseLeave={() => setHoveredModel(null)}
                onClick={() => onSelectModel?.(item.model)}
              >
                {/* Glow ring for recommended model */}
                {isRecommended && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={22}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2.5"
                    strokeDasharray="3 3"
                    className="quadrant-recommended-pulse"
                  />
                )}

                {/* Outer ring on hover/selected */}
                {(isSelected || isHovered) && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={18}
                    fill="none"
                    stroke={circleColor}
                    strokeWidth="2"
                    opacity={0.7}
                  />
                )}

                {/* Main point */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isRecommended ? 12 : 9}
                  fill={circleColor}
                  stroke="var(--quadrant-point-stroke)"
                  strokeWidth="2.5"
                />

                {/* Point label */}
                <text
                  x={labelX}
                  y={labelY}
                  textAnchor={labelAnchor}
                  className={`quadrant-point-label ${
                    isRecommended ? "quadrant-point-label--recommended" : ""
                  }`}
                >
                  {isRecommended ? `⭐ ${item.model}` : item.model}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay with theme variables */}
        {hoveredModel && (
          <div className="quadrant-tooltip">
            <strong>{hoveredModel.model}</strong>
            <div className="quadrant-tooltip-grid">
              <span>Copertura Privacy:</span>
              <strong>{formatPercent(hoveredModel.recall)}</strong>
              <span>Zero-Leak Documenti:</span>
              <strong>{formatPercent(hoveredModel.zeroLeakDocs)}</strong>
              <span>Affidabilità Esecuzione:</span>
              <strong>{formatPercent(hoveredModel.successRate)}</strong>
              <span>Latenza p95:</span>
              <strong>{formatMs(hoveredModel.latencyP95)}</strong>
            </div>
            <div
              className={`quadrant-tooltip-verdict quadrant-tooltip-verdict--${hoveredModel.tone}`}
            >
              {hoveredModel.badge} {hoveredModel.verdict}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ExecutiveDecisionQuadrant;
