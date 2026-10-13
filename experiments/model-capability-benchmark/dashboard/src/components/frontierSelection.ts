import type { FrontierPoint } from '../types';

const RESOURCE_METRICS = [
  ['parameters_b', 'pareto_parameters'],
  ['artifact_size_bytes', 'pareto_artifact_size'],
  ['peak_rss_bytes', 'pareto_peak_rss'],
  ['latency_p50_ms', 'pareto_latency'],
] as const;

function isMeasured(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * The projected Pareto flags describe the full dataset. Filtered visualizations
 * must compare only the current cohort, otherwise removed models can still
 * dominate a visible point.
 */
export function recalculateFrontier(points: FrontierPoint[]): FrontierPoint[] {
  return points.map((point) => {
    const flags = RESOURCE_METRICS.map(([metric]) => {
      const resource = point[metric];
      if (!isMeasured(resource) || !isMeasured(point.quality)) return false;
      return !points.some((other) => {
        const otherResource = other[metric];
        return (
          isMeasured(otherResource) &&
          isMeasured(other.quality) &&
          otherResource <= resource &&
          other.quality >= point.quality! &&
          (otherResource < resource || other.quality > point.quality!)
        );
      });
    });
    return {
      ...point,
      pareto_parameters: flags[0],
      pareto_artifact_size: flags[1],
      pareto_peak_rss: flags[2],
      pareto_latency: flags[3],
    };
  });
}

export function filterFrontierSelection(
  points: FrontierPoint[],
  signatures: readonly string[] | null,
): FrontierPoint[] {
  if (signatures === null) return points;
  const allowed = new Set(signatures);
  return points.filter((point) => allowed.has(point.model_signature));
}
