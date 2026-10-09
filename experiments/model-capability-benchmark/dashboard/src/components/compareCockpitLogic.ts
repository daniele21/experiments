import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { leaderIndices, QUALITY_TIE_TOLERANCE } from './compareThreeLogic.ts';

export type CockpitMetric = 'quality' | 'speed' | 'reliability' | 'memory';
export type CockpitModels = [DecisionModelSummary, DecisionModelSummary] | [DecisionModelSummary, DecisionModelSummary, DecisionModelSummary];

export interface CockpitDataset {
  key: string;
  dataset: string;
  capability: string;
  values: Array<number | null>;
  samples: number[];
  winner: number | null;
  tied: boolean;
  shared: boolean;
}

export function cockpitMetricValue(model: DecisionModelSummary, metric: CockpitMetric): number | null {
  const value = metric === 'quality' ? model.overall_quality_score :
    metric === 'speed' ? model.latency_p50_ms :
    metric === 'reliability' ? model.failure_rate :
    model.resource_summary?.process_rss_bytes_peak;
  if (typeof value !== 'number' || !Number.isFinite(value) || (metric === 'memory' && value <= 0)) return null;
  return value;
}

export function cockpitMetricLeader(models: CockpitModels, metric: CockpitMetric): number | null {
  const values = models.map(model => cockpitMetricValue(model, metric));
  // Incomplete coverage must not be silently interpreted as a leaderboard.
  const leaders = leaderIndices(values, metric !== 'quality', metric === 'quality' ? QUALITY_TIE_TOLERANCE : 0);
  return leaders.length === 1 ? leaders[0] : null;
}

export function cockpitDatasets(models: CockpitModels, rows: DecisionDatasetSummary[]) {
  const maps = models.map(model => new Map(
    rows.filter(row => row.model_key === model.model_key).map(row => [
      row.capability_id + '::' + row.dataset_id, row,
    ]),
  ));
  const allKeys = [...new Set(maps.flatMap(map => [...map.keys()]))].sort();
  const datasets: CockpitDataset[] = allKeys.map(key => {
    const records = maps.map(map => map.get(key));
    const values = records.map(row =>
      typeof row?.normalized_quality_score === 'number' && Number.isFinite(row.normalized_quality_score)
        ? row.normalized_quality_score : null);
    const leaders = leaderIndices(values, false, QUALITY_TIE_TOLERANCE);
    const shared = values.every(value => value != null);
    const first = records.find(Boolean);
    return {
      key, dataset: first?.dataset_id ?? key,
      capability: first?.capability_id ?? '',
      values, samples: records.map(row => row?.sample_count ?? 0),
      winner: shared && leaders.length === 1 ? leaders[0] : null,
      tied: shared && leaders.length > 1,
      shared,
    };
  });
  return {
    datasets,
    union: datasets.length,
    shared: datasets.filter(row => row.shared).length,
    wins: models.map((_, i) => datasets.filter(row => row.winner === i).length),
    ties: datasets.filter(row => row.tied).length,
  };
}

export function cockpitDecision(models: CockpitModels, shared: number, union: number) {
  const letters = ['A', 'B', 'C'];
  const quality = cockpitMetricLeader(models, 'quality');
  const speed = cockpitMetricLeader(models, 'speed');
  const memory = cockpitMetricLeader(models, 'memory');
  const failures = cockpitMetricLeader(models, 'reliability');
  const samePolicy = models.every(m => m.quality_policy_id === models[0].quality_policy_id);
  const comparable = samePolicy && shared > 0 && union === shared && models.every(m => m.quality_coverage_complete);
  if (!comparable) return {
    title: 'Evidence coverage needs review',
    description: 'Dataset coverage or quality policy differs. Inspect the missing results before declaring a winner.',
  };
  if (quality != null && speed != null && memory != null && failures != null &&
      quality === speed && speed === memory && memory === failures) {
    return {
      title: 'Model ' + letters[quality] + ' leads across observed metrics',
      description: 'Quality, observed P50, benchmark failure rate and measured RSS favor the same model. Host differences still matter.',
    };
  }
  if (quality != null && speed != null && quality !== speed) {
    return {
      title: letters[quality] + ' for quality · ' + letters[speed] + ' for observed speed',
      description: memory == null
        ? 'No universal winner. Check reliability and task-level evidence; memory comparability is incomplete.'
        : 'No universal winner. ' + letters[memory] + ' uses the least measured process RAM; verify test environments.',
    };
  }
  if (quality != null && memory != null && quality !== memory) {
    return {
      title: letters[quality] + ' for quality · ' + letters[memory] + ' for measured RAM',
      description: 'The strongest quality result and lowest measured process footprint belong to different models.',
    };
  }
  return {
    title: 'Choose by task and deployment context',
    description: 'The evidence does not support a universal winner across quality, observed speed and hardware requirements.',
  };
}
