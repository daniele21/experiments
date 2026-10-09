import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import type { DecisionModelSummary } from '../types';
import { finitePositive, getHardwareComparability, peakAttribution, peakRss } from './hardwareEvidence.ts';

function example(name: string, peak: number | null, cpu: string, runIds = [name + '-run']): DecisionModelSummary {
  return {
    model_key: name,
    deployment: 'local',
    runtime_key: 'korgis',
    execution_profile: 'core',
    current_run_ids: runIds,
    execution_environment: {
      run_id: name + '-run',
      cpu_model: cpu,
      system: 'darwin',
      machine: 'arm64',
      release: '26.0',
      total_memory_bytes: 36 * 1024**3,
    },
    resource_summary: { process_cpu_percent_avg: 140, process_rss_bytes_peak: peak, scope: 'owned_backend_process', sampling_error_count: 0 },
  } as DecisionModelSummary;
}

describe('hardware and memory evidence', () => {
  it('never assumes missing or zero RSS is measured memory', () => {
    assert.equal(finitePositive(null), false);
    assert.equal(peakRss(example('api', null, 'Apple M3')), null);
    assert.equal(peakRss(example('invalid', 0, 'Apple M3')), null);
  });

  it('attributes a single-run legacy export correctly', () => {
    const a = example('a', 6 * 1024**3, 'Apple M3 Pro');
    const result = peakAttribution(a);
    assert.equal(result.provenance, 'single-run');
    assert.equal(result.peakRunId, 'a-run');
  });

  it('does not assign the latest device to a multi-run peak', () => {
    const a = example('a', 7 * 1024**3, 'Apple M4 Max', ['other-run', 'a-run']);
    const result = peakAttribution(a);
    assert.equal(result.provenance, 'latest-only');
    assert.equal(getHardwareComparability([a, example('b', 5 * 1024**3, 'Apple M4 Max')]).status, 'unknown');
    a.resource_summary.peak_run_id = 'other-run';
    a.resource_summary.peak_execution_environment = {
      ...a.execution_environment!,
      run_id: 'other-run',
      cpu_model: 'Apple M3 Pro',
    };
    assert.equal(peakAttribution(a).environment?.cpu_model, 'Apple M3 Pro');
    assert.equal(getHardwareComparability([a, example('b', 5 * 1024**3, 'Apple M4 Max')]).status, 'mismatch');
  });

  it('recognizes comparable peak hosts but still warns on runtime mismatches', () => {
    const a = example('a', 4 * 1024**3, 'Apple M3 Pro');
    const b = example('b', 8 * 1024**3, 'Apple M3 Pro');
    assert.equal(getHardwareComparability([a,b]).status, 'matched');
    b.runtime_key = 'different-runtime';
    assert.match(getHardwareComparability([a,b]).detail, /Runtime implementations differ/);
    b.resource_summary.sampling_error_count = 1;
    assert.equal(getHardwareComparability([a,b]).status, 'unknown');
  });

  it('does not rank a three-model selection with missing memory', () => {
    const a = example('a', 5 * 1024**3, 'Apple M3 Pro');
    const b = example('b', null, 'Apple M3 Pro');
    const c = example('c', 6 * 1024**3, 'Apple M3 Pro');
    assert.equal(getHardwareComparability([a,b,c]).status, 'unknown');
  });
});
