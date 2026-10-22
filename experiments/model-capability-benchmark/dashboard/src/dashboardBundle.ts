import type { DashboardBundle } from './types';

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseDashboardBundle(value: unknown): DashboardBundle {
  if (!record(value) || value.schema_version !== '1' || typeof value.generated_at_utc !== 'string'
    || !record(value.overview)) {
    throw new Error('Unsupported or incomplete dashboard data file');
  }
  const overview = value.overview;
  if (!['models', 'capabilities', 'cells', 'runs'].every((key) => Array.isArray(overview[key]))
    || !['capabilities', 'models', 'runs'].every((key) => record(value[key])
      && Object.values(value[key]).every(record))) {
    throw new Error('Unsupported or incomplete dashboard data file');
  }
  return value as unknown as DashboardBundle;
}
