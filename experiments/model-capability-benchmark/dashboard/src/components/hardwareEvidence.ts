import type { DecisionModelSummary, ExecutionEnvironment } from '../types';

export function finitePositive(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

export function peakRss(model: DecisionModelSummary): number | null {
  const value = model.resource_summary?.process_rss_bytes_peak;
  return finitePositive(value) ? value : null;
}

export interface PeakAttribution {
  environment: ExecutionEnvironment | null;
  provenance: 'recorded-peak-run' | 'single-run' | 'latest-only' | 'unavailable';
  peakRunId: string | null;
}

export function peakAttribution(model: DecisionModelSummary): PeakAttribution {
  const peak = peakRss(model);
  const resource = model.resource_summary;
  const env = resource?.peak_execution_environment ?? null;
  const peakRunId = resource?.peak_run_id ?? null;
  if (peak != null && peakRunId && env) {
    return { environment: env, provenance: 'recorded-peak-run', peakRunId };
  }
  const latest = model.execution_environment ?? null;
  const runIds = model.current_run_ids ?? [];
  if (peak != null && runIds.length === 1 && latest?.run_id === runIds[0]) {
    return { environment: latest, provenance: 'single-run', peakRunId: runIds[0] };
  }
  return {
    environment: latest,
    provenance: peak == null ? 'unavailable' : 'latest-only',
    peakRunId,
  };
}

export function getHardwareComparability(models: DecisionModelSummary[]): {
  status: 'matched' | 'mismatch' | 'unknown';
  detail: string;
} {
  const withMemory = models.filter(m => peakRss(m) != null);
  if (withMemory.length < 2) {
    return { status: 'unknown', detail: 'At least two measured process RSS peaks are needed.' };
  }
  if (withMemory.length !== models.length) {
    return { status: 'unknown', detail: 'Not every selected model has observed memory telemetry. Compare only the measured models.' };
  }
  const attributions = withMemory.map(peakAttribution);
  if (attributions.some(x => !['recorded-peak-run', 'single-run'].includes(x.provenance))) {
    return { status: 'unknown', detail: 'The device associated with at least one peak was not recorded. Older exports may need regeneration.' };
  }
  const hardware = attributions.map(x => x.environment);
  if (hardware.some(x => !x?.cpu_model || !x.machine || !x.system)) {
    return { status: 'unknown', detail: 'The host CPU, architecture or operating system was not recorded for every peak.' };
  }
  const first = hardware[0]!;
  if (hardware.some(x => !finitePositive(x?.total_memory_bytes))) {
    return { status: 'unknown', detail: 'Peak-run host memory capacity is missing for one or more models.' };
  }
  if (!hardware.every(x => x?.cpu_model === first.cpu_model && x?.machine === first.machine && x?.system === first.system &&
    (x?.total_memory_bytes == null || first.total_memory_bytes == null || x.total_memory_bytes === first.total_memory_bytes))) {
    return { status: 'mismatch', detail: 'Different host hardware was used for the observed peak runs. Memory differences are descriptive, not directly controlled.' };
  }
  const scopes = withMemory.map(m => m.resource_summary?.scope).filter(Boolean);
  if (scopes.length !== withMemory.length || scopes.includes('mixed') || scopes.includes('unavailable') || new Set(scopes).size > 1) {
    return { status: 'unknown', detail: 'Resource measurements use different or mixed scopes. Avoid ranking memory efficiency.' };
  }
  const hasErrors = withMemory.some(m => (m.resource_summary?.sampling_error_count ?? 0) > 0);
  if (hasErrors) {
    return { status: 'unknown', detail: 'Some resource samples failed. Measured peaks may be incomplete.' };
  }
  const runtimes = new Set(withMemory.map(m => m.runtime_key));
  return {
    status: 'matched',
    detail: runtimes.size > 1
      ? 'Reported peak-run hardware specs match. Runtime implementations differ, so memory results are still observational.'
      : 'Reported peak-run hardware specs and runtime keys match. Run load and configuration may still vary.',
  };
}
