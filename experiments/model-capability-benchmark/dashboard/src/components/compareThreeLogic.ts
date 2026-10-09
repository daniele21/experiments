import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';

export type ComparePreference = 'balanced' | 'quality' | 'speed' | 'reliability';
export type ModelPosition = 'A' | 'B' | 'C';
export type ThreeModels = [DecisionModelSummary, DecisionModelSummary, DecisionModelSummary];
export type ThreeScores = [number, number, number];

export interface ThreeDatasetRow {
  key: string;
  capability: string;
  dataset: string;
  scores: ThreeScores;
  samples: [number, number, number];
  spread: number;
  winners: number[];
}
export const QUALITY_TIE_TOLERANCE = 0.05;

export function leaderIndices(values: Array<number | null | undefined>, lowerBetter: boolean, epsilon = 0): number[] {
  if (!values.length || values.some(value => value == null || !Number.isFinite(value))) return [];
  const numbers = values as number[];
  const target = lowerBetter ? Math.min(...numbers) : Math.max(...numbers);
  return numbers.flatMap((value, index) => Math.abs(value - target) <= epsilon ? [index] : []);
}

export function sharedThreeDatasets(rows: DecisionDatasetSummary[], models: ThreeModels) {
  const keys = models.map(model => model.model_key);
  const maps = keys.map(key => new Map(
    rows.filter(row => row.model_key === key).map(row => [row.capability_id + '::' + row.dataset_id, row]),
  ));
  const union = new Set(maps.flatMap(map => [...map.keys()]));
  const shared: ThreeDatasetRow[] = [];
  for (const key of union) {
    const values = maps.map(map => map.get(key)?.normalized_quality_score);
    if (values.some(value => value == null || !Number.isFinite(value))) continue;
    const scores = values as ThreeScores;
    const reference = maps[0].get(key) ?? maps[1].get(key) ?? maps[2].get(key);
    if (!reference) continue;
    shared.push({
      key, capability: reference.capability_id, dataset: reference.dataset_id,
      scores, samples: maps.map(map => map.get(key)?.sample_count ?? 0) as [number, number, number],
      spread: Math.max(...scores) - Math.min(...scores),
      winners: leaderIndices(scores, false, QUALITY_TIE_TOLERANCE),
    });
  }
  shared.sort((a, b) => b.spread - a.spread || a.key.localeCompare(b.key));
  const wins = keys.map((_, index) => shared.filter(row => row.winners.length === 1 && row.winners[0] === index).length) as [number, number, number];
  const ties = shared.filter(row => row.winners.length !== 1).length;
  return { shared, unionCount: union.size, wins, ties, excludedCount: union.size - shared.length };
}

export function threeDecisionInsight(models: ThreeModels, preference: ComparePreference, shared: number, union: number) {
  const lead = (metric: 'quality' | 'speed' | 'reliability') => {
    const values = models.map(model => metric === 'quality' ? model.overall_quality_score : metric === 'speed' ? model.latency_p50_ms : model.failure_rate);
    return leaderIndices(values, metric !== 'quality', metric === 'quality' ? QUALITY_TIE_TOLERANCE : 0);
  };
  const [quality, speed, reliability] = [lead('quality'), lead('speed'), lead('reliability')];
  const samePolicy = models.every(model => model.quality_policy_id === models[0].quality_policy_id);
  const coverage = models.every(model => model.quality_coverage_complete) && shared > 0 && shared === union;
  const label = (index: number) => 'Model ' + ('ABC'[index]) + ' (' + models[index].model_key + ')';
  if (preference === 'quality') {
    return quality.length === 1
      ? { title: label(quality[0]) + ' leads on aggregate quality', detail: 'This prioritizes the observed benchmark score. Compare the shared datasets and coverage before making a deployment decision.' }
      : { title: 'No unique aggregate-quality leader', detail: 'There is a tie or incomplete quality evidence across the three models.' };
  }
  if (preference === 'speed') {
    return speed.length === 1
      ? { title: label(speed[0]) + ' has lowest observed P50 latency', detail: 'Observed latency is hardware- and runtime-dependent; it is not an intrinsic speed ranking without matched execution conditions.' }
      : { title: 'No unique observed-speed leader', detail: 'At least one P50 value is missing or the fastest observed results are tied.' };
  }
  if (preference === 'reliability') {
    return reliability.length === 1
      ? { title: label(reliability[0]) + ' has lowest observed failure rate', detail: 'This concerns benchmark failures, not a guarantee of production reliability. Inspect failures and sample counts.' }
      : { title: 'No unique observed-reliability leader', detail: 'At least one failure-rate value is missing or the best results are tied.' };
  }
  if (!samePolicy || !coverage) {
    return { title: 'Compare cautiously: evidence coverage differs', detail: 'Not every dataset is shared or the quality policies/coverage differ. Task-level scores remain descriptive until the evidence is aligned.' };
  }
  if (quality.length === 1 && speed.length === 1 && reliability.length === 1 &&
      quality[0] === speed[0] && speed[0] === reliability[0]) {
    return { title: label(quality[0]) + ' leads across all three observed metrics', detail: 'Aggregate quality, observed latency and benchmark failures favor the same model. Confirm equal execution conditions before treating the speed result as generalizable.' };
  }
  return { title: 'Three models, different strengths — no universal winner', detail: 'Use the quality, observed-speed and reliability leaders alongside the task-level scorecards. The balanced view does not invent a composite score.' };
}
