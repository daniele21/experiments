import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { leaderIndices, sharedThreeDatasets, threeDecisionInsight } from './compareThreeLogic.ts';

function model(model_key: string, quality: number | null, p50: number, failure: number): DecisionModelSummary {
  return {
    model_key, overall_quality_score: quality, latency_p50_ms: p50, failure_rate: failure,
    quality_policy_id: 'core-quality-v1', quality_coverage_complete: true,
  } as DecisionModelSummary;
}
function dataset(model_key: string, dataset_id: string, normalized_quality_score: number | null, sample_count = 10): DecisionDatasetSummary {
  return {
    model_key, dataset_id, capability_id: 'intent-classification',
    normalized_quality_score, sample_count,
  } as DecisionDatasetSummary;
}

describe('three-model comparison decisions', () => {
  const models = [model('a', 60, 250, .01), model('b', 70, 1200, .02), model('c', 65, 600, .005)] as const;

  it('identifies winner and ties without turning missing data into zero', () => {
    assert.deepEqual(leaderIndices([12, 15, 13], false), [1]);
    assert.deepEqual(leaderIndices([.01, .01, .02], true), [0, 1]);
    assert.deepEqual(leaderIndices([0, 0.04, 0.3], false, .05), [2]);
    assert.deepEqual(leaderIndices([null, 3, 4], false), []);
    assert.deepEqual(leaderIndices([0, 0, 0], true), [0, 1, 2]);
  });

  it('compares only shared valid scores and counts missing dataset coverage', () => {
    const rows = [
      dataset('a', 'one', 50), dataset('b', 'one', 60), dataset('c', 'one', 70),
      dataset('a', 'two', 90), dataset('b', 'two', 89.98), dataset('c', 'two', 20),
      dataset('a', 'partial', 20), dataset('b', 'partial', 22),
      dataset('a', 'missing', null), dataset('b', 'missing', 50), dataset('c', 'missing', 80),
    ];
    const result = sharedThreeDatasets(rows, [...models],);
    assert.equal(result.unionCount, 4);
    assert.equal(result.shared.length, 2);
    assert.deepEqual(result.wins, [0, 0, 1]);
    assert.equal(result.ties, 1);
    assert.equal(result.excludedCount, 2);
    assert.equal(result.shared[0].dataset, 'two');
    assert.equal(result.shared[0].spread, 70);
    assert.deepEqual(result.shared[0].winners, [0, 1]);
    assert.deepEqual(result.shared[1].winners, [2]);
  });

  it('does not manufacture a balanced winner when metrics disagree', () => {
    const decision = threeDecisionInsight([...models], 'balanced', 2, 2);
    assert.match(decision.title, /no universal winner/);
    assert.match(threeDecisionInsight([...models], 'quality', 2, 2).title, /Model B/);
    assert.match(threeDecisionInsight([...models], 'speed', 2, 2).title, /Model A/);
    assert.match(threeDecisionInsight([...models], 'reliability', 2, 2).title, /Model C/);
  });

  it('makes incomplete or mismatched quality evidence explicit', () => {
    assert.match(threeDecisionInsight([...models], 'balanced', 1, 3).title, /evidence coverage differs/);
    const mixed = [models[0], {...models[1], quality_policy_id:'different'}, models[2]] as [DecisionModelSummary,DecisionModelSummary,DecisionModelSummary];
    assert.match(threeDecisionInsight(mixed, 'balanced', 3, 3).title, /evidence coverage differs/);
  });

  it('does not pick leaders where any metric is missing', () => {
    const incomplete = [model('a', 50, 50, 0), model('b', null, 60, .01), model('c', 60, 70, .02)] as [DecisionModelSummary,DecisionModelSummary,DecisionModelSummary];
    assert.match(threeDecisionInsight(incomplete, 'quality', 0, 1).title, /No unique/);
    assert.deepEqual(sharedThreeDatasets([], incomplete).wins, [0,0,0]);
  });
});
