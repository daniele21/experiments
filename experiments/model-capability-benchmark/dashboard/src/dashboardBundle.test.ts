import assert from 'node:assert/strict';
import test from 'node:test';
import { parseDashboardBundle } from './dashboardBundle.ts';

const valid = {
  schema_version: '1', generated_at_utc: '2026-10-22T00:00:00Z',
  overview: { models: [], capabilities: [], cells: [], runs: [] },
  capabilities: { cap: {} }, models: { model: {} }, runs: { run: {} },
};

test('accepts one snapshot containing all route maps', () => {
  assert.equal(parseDashboardBundle(valid), valid);
});

test('rejects unsupported, missing or malformed route data', () => {
  for (const invalid of [null, {}, { ...valid, schema_version: '2' },
    { ...valid, models: [] }, { ...valid, runs: null }, { ...valid, capabilities: { cap: 'bad' } },
    { ...valid, overview: { ...valid.overview, cells: 'bad' } }]) {
    assert.throws(() => parseDashboardBundle(invalid), /Unsupported or incomplete/);
  }
});
