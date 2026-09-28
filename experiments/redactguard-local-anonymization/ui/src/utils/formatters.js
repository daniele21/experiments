/**
 * formatters.js
 *
 * Reusable formatting and data normalization utilities.
 */

/**
 * Extracts micro summary object or falls back to the object itself.
 */
export function micro(summary) {
  return summary?.micro ?? summary ?? {};
}

/**
 * Normalizes a number into a 0..100 percentage value.
 * Handles both ratio (0.85 -> 85) and percentage format (85 -> 85).
 */
export function percentValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  const numeric = Number(value);
  return numeric <= 1.000001 ? numeric * 100 : numeric;
}

/**
 * Formats a value as a percentage string (e.g. "85.2%").
 */
export function formatPercent(value, digits = 1) {
  const normalized = percentValue(value);
  return normalized === null ? "—" : `${normalized.toFixed(digits)}%`;
}

/**
 * Formats a millisecond latency value to either ms or seconds.
 */
export function formatMs(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const numeric = Number(value);
  return numeric >= 1000 ? `${(numeric / 1000).toFixed(2)} s` : `${numeric.toFixed(0)} ms`;
}

/**
 * Formats an ISO date string into a localized medium date & short time.
 */
export function formatDate(value) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/**
 * Extracts the trailing dataset name from a path or string.
 */
export function shortDataset(value) {
  if (!value) return "dataset";
  const parts = String(value).split(/[\\/]/).filter(Boolean);
  return parts.at(-1) ?? value;
}

/**
 * Clamps a number between min and max bounds.
 */
export function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}
