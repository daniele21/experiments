import { clamp, percentValue } from "../utils/formatters";

/**
 * Visual mini progress bar for showing ratios in tables.
 */
export function MiniBar({ value, inverse = false }) {
  const percentage = percentValue(value);
  const width = percentage === null ? 0 : clamp(percentage);
  return (
    <div className="mini-bar" aria-hidden="true">
      <span
        className={inverse ? "mini-bar__fill mini-bar__fill--risk" : "mini-bar__fill"}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

/**
 * Metric card displaying a primary value, label, optional hint, and color tone.
 */
export function MetricCard({ label, value, hint, tone = "neutral" }) {
  return (
    <div className={`metric-card metric-card--${tone}`}>
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
