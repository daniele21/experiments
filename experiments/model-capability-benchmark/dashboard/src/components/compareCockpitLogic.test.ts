import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import type { DecisionDatasetSummary, DecisionModelSummary } from '../types';
import { cockpitDatasets, cockpitDecision, cockpitMetricLeader, cockpitMetricValue } from './compareCockpitLogic.ts';

function model(key: string, quality: number | null, speed: number | null, rss: number | null): DecisionModelSummary {
  return {
    model_key: key, quality_policy_id: 'shared', quality_coverage_complete: true,
    overall_quality_score: quality, latency_p50_ms: speed, failure_rate: 0.01,
    resource_summary: { process_rss_bytes_peak: rss },
  } as DecisionModelSummary;
}
function dataset(key: string, task: string, value: number | null): DecisionDatasetSummary {
  return { model_key: key, capability_id: 'test-capability', dataset_id: task,
    normalized_quality_score: value, sample_count: 12 } as DecisionDatasetSummary;
}
describe('responsive cockpit evidence — 2 and 3 models', () => {
  const a = model('a', 70, 200, 4e9), b = model('b', 75, 400, 7e9), c = model('c', 90, 1000, 9e9);
  it('selects observed metric leaders in either model count', () => {
    assert.equal(cockpitMetricLeader([a,b], 'quality'), 1);
    assert.equal(cockpitMetricLeader([a,b,c], 'quality'), 2);
    assert.equal(cockpitMetricLeader([a,b,c], 'speed'), 0);
    assert.equal(cockpitMetricLeader([a,b,c], 'memory'), 0);
  });
  it('rejects empty, NaN and unobserved memory without creating false winners', () => {
    const missing = model('api', 95, null, null);
    assert.equal(cockpitMetricLeader([a,missing], 'speed'), null);
    assert.equal(cockpitMetricLeader([a,b,missing], 'memory'), null);
    assert.equal(cockpitMetricValue(missing, 'memory'), null);
    assert.equal(cockpitMetricValue(model('bad', 0, 0, 0), 'memory'), null);
    assert.equal(cockpitMetricValue(model('nan', Number.NaN, 10, null), 'quality'), null);
  });
  it('does not imply a ranking for ties or near-equal quality results', () => {
    const tie = model('tie', 70.03, 100, 3e9);
    assert.equal(cockpitMetricLeader([a,tie], 'quality'), null);
    assert.equal(cockpitMetricLeader([a,a], 'speed'), null);
  });
  it('shows union datasets with unavailable cells but scores wins only on shared evidence', () => {
    const rows = [
      dataset('a','math',80),dataset('b','math',75),dataset('c','math',90),
      dataset('a','schema',99),dataset('b','schema',99.03),dataset('c','schema',90),
      dataset('a','partial',75),dataset('b','partial',67),
      dataset('a','unscored',null),dataset('b','unscored',50),dataset('c','unscored',40),
    ];
    const three = cockpitDatasets([a,b,c],rows);
    assert.equal(three.union,4);
    assert.equal(three.shared,2);
    assert.deepEqual(three.wins,[0,0,1]);
    assert.equal(three.ties,1);
    assert.equal(three.datasets.find(row=>row.dataset==='partial')?.winner,null);
    assert.equal(three.datasets.find(row=>row.dataset==='unscored')?.values[0],null);
    assert.match(cockpitDecision([a,b,c],three.shared,three.union).title,/coverage/i);
    const two = cockpitDatasets([a,b],rows);
    assert.equal(two.union,4);
    assert.equal(two.shared,3);
    assert.deepEqual(two.wins,[2,0]);
    assert.equal(two.ties,1);
  });
  it('creates a conservative executive recommendation with shared coverage', () => {
    const decision = cockpitDecision([a,b,c],5,5);
    assert.match(decision.title,/C for quality.*A for observed speed/);
    assert.match(decision.description,/No universal winner/);
    const policies = [a,{...b,quality_policy_id:'different'}] as [DecisionModelSummary,DecisionModelSummary];
    assert.match(cockpitDecision(policies,5,5).title,/coverage needs review/i);
  });
  it('does not depend on hard-coded dataset names or ordering', () => {
    const rows = [dataset('b','zebra-task',52),dataset('a','zebra-task',56),
      dataset('a','aaa-new-task',45),dataset('b','aaa-new-task',49)];
    const summary = cockpitDatasets([a,b],rows);
    assert.deepEqual(summary.datasets.map(row=>row.dataset),['aaa-new-task','zebra-task']);
    assert.deepEqual(summary.wins,[1,1]);
  });
});
