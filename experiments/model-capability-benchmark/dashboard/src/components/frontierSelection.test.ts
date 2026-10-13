import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import type { FrontierPoint } from '../types';
import { filterFrontierSelection, recalculateFrontier } from './frontierSelection.ts';

function point(
  id: string, cost: number | null, quality: number | null,
  other: Partial<FrontierPoint> = {},
): FrontierPoint {
  return {
    model_key: id, model_signature: id, family: 'qwen', parameters_b: cost,
    quantization: 'q4', artifact_size_bytes: cost, peak_rss_bytes: cost,
    latency_p50_ms: cost, quality, deployment: 'local', compression_group: null,
    pareto_parameters: false, pareto_artifact_size: false,
    pareto_peak_rss: false, pareto_latency: false, ...other,
  };
}

describe('Frontier manually selected model cohort', () => {
  it('includes every model by default and distinguishes variants by signature', () => {
    const models = [point('first', 2, 60), point('second', 4, 75, { model_key: 'first' })];
    assert.equal(filterFrontierSelection(models, null).length, 2);
    assert.deepEqual(filterFrontierSelection(models, ['second']).map((p) => p.model_signature), ['second']);
    assert.deepEqual(filterFrontierSelection(models, []), []);
  });

  it('recomputes domination after excluding a model', () => {
    const models = [
      point('small', 1, 60),
      point('dominated', 4, 55),
      point('large', 9, 80),
    ];
    assert.equal(recalculateFrontier(models)[1].pareto_parameters, false);
    const subset = filterFrontierSelection(models, ['dominated', 'large']);
    const recalculated = recalculateFrontier(subset);
    assert.equal(recalculated[0].pareto_parameters, true);
    assert.equal(recalculated[1].pareto_parameters, true);
    assert.equal(recalculated[0].pareto_latency, true);
  });

  it('ties stay efficient; missing metrics never become Pareto evidence', () => {
    const models = [point('a', 2, 75), point('b', 2, 75), point('missing', null, 100)];
    const results = recalculateFrontier(models);
    assert.equal(results[0].pareto_parameters, true);
    assert.equal(results[1].pareto_parameters, true);
    assert.equal(results[2].pareto_parameters, false);
  });

  it('checks each deployment dimension independently', () => {
    const models = [
      point('fast', 4, 80, { latency_p50_ms: 100 }),
      point('small', 2, 70, { latency_p50_ms: 600 }),
    ];
    const results = recalculateFrontier(models);
    assert.equal(results[0].pareto_parameters, true);
    assert.equal(results[1].pareto_parameters, true);
    assert.equal(results[0].pareto_latency, true);
    assert.equal(results[1].pareto_latency, false);
  });
});
