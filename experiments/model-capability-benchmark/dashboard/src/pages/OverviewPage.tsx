import {
  BadgeDollarSign,
  Cpu,
  Database,
  Laptop,
  MemoryStick,
  Trophy,
  Zap,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { overview } from '../data';
import type {
  DecisionModelSummary,
  DecisionPayload,
  OverviewPayload,
} from '../types';
import { bytes, cpu, milliseconds, score, usd } from '../utils';
import {
  DatasetHeatmap,
  DatasetPerformanceLandscape,
  DeploymentBadge,
  MethodologyAccordion,
  MetricCard,
  QualityLeaderboard,
  TradeoffScatter,
} from '../components/DecisionComponents';
import { AppLink, PageHeader } from '../components/Shell';

function fallbackDecision(payload: OverviewPayload): DecisionPayload {
  const byModel = new Map<string, typeof payload.cells>();
  for (const cell of payload.cells) {
    byModel.set(cell.model_signature, [
      ...(byModel.get(cell.model_signature) ?? []),
      cell,
    ]);
  }
  const modelSummaries: DecisionModelSummary[] = payload.models.map((model) => {
    const cells = byModel.get(model.model_signature) ?? [];
    const values = cells
      .map((cell) => cell.primary_value)
      .filter((value): value is number => value != null);
    const quality = values.length
      ? (values.reduce((total, value) => total + value, 0) / values.length) * 100
      : null;
    const resources = cells
      .map((cell) => cell.resource_summary)
      .filter((value) => value != null);
    return {
      ...model,
      quality_policy_id: 'fixture-fallback',
      overall_quality_score: quality,
      quality_coverage_capabilities: cells.length,
      quality_total_capabilities: payload.capabilities.length,
      quality_coverage_datasets: 0,
      quality_total_datasets: 0,
      quality_coverage_complete: cells.length === payload.capabilities.length,
      observed_case_count: cells.reduce((total, cell) => total + cell.sample_count, 0),
      latency_p50_ms: null,
      latency_p95_ms: null,
      latency_mean_ms: null,
      provider_cost_known: false,
      provider_cost_total_usd: null,
      provider_cost_per_case_usd: null,
      provider_cost_per_1k_cases_usd: null,
      input_tokens_total: null,
      output_tokens_total: null,
      failure_count: cells.reduce((total, cell) => total + cell.failure_count, 0),
      failure_rate: null,
      execution_count: new Set(cells.map((cell) => cell.execution_signature)).size,
      execution_environment: null,
      resource_summary: {
        process_cpu_percent_avg:
          resources[0]?.process_cpu_percent_avg ?? null,
        process_rss_bytes_peak:
          resources[0]?.process_rss_bytes_peak ?? null,
      },
      latest_completed_at_utc: cells[0]?.completed_at_utc ?? null,
      current_run_ids: cells.map((cell) => cell.run_id),
      observed_quality_latency_pareto: false,
      known_provider_cost_quality_pareto: false,
    };
  });
  return {
    schema_version: 'fixture',
    quality_policy: {
      quality_policy_id: 'fixture-fallback',
      label: 'Fixture fallback',
      aggregation: 'mean',
      coverage_requirement: 'complete',
      normalization: 'unit metrics to 0-100',
    },
    cohort_policy: {
      policy_id: 'fixture',
      description: 'Fixture payload',
      benchmark_signatures: {},
    },
    model_summaries: modelSummaries,
    capability_summaries: [],
    dataset_summaries: [],
  };
}

export function OverviewPage() {
  const decision = overview.decision ?? fallbackDecision(overview);
  const [deployment, setDeployment] = useState<'all' | 'local' | 'api'>('all');
  const visibleModels = useMemo(
    () =>
      decision.model_summaries.filter(
        (model) => deployment === 'all' || model.deployment === deployment,
      ),
    [decision.model_summaries, deployment],
  );
  const ranked = [...visibleModels].sort(
    (a, b) => (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1),
  );
  const bestQuality = ranked.find((model) => model.quality_coverage_complete) ?? ranked[0];
  const bestLocal = ranked.find((model) => model.deployment === 'local');
  const fastest = [...visibleModels]
    .filter((model) => model.latency_p50_ms != null)
    .sort((a, b) => Number(a.latency_p50_ms) - Number(b.latency_p50_ms))[0];
  const cheapest = [...visibleModels]
    .filter(
      (model) =>
        model.provider_cost_known &&
        model.provider_cost_per_1k_cases_usd != null,
    )
    .sort(
      (a, b) =>
        Number(a.provider_cost_per_1k_cases_usd) -
        Number(b.provider_cost_per_1k_cases_usd),
    )[0];
  const [selectedSignature, setSelectedSignature] = useState<string | null>(
    bestLocal?.model_signature ?? bestQuality?.model_signature ?? null,
  );
  const selected =
    visibleModels.find((model) => model.model_signature === selectedSignature) ??
    ranked[0] ??
    null;

  const selectModel = (signature: string) => setSelectedSignature(signature);

  return (
    <>
      {overview.fixture ? (
        <div className="fixture-banner">
          Fixture preview · run a projected benchmark to populate measured latency,
          cost and dataset analytics.
        </div>
      ) : null}

      <PageHeader
        eyebrow="Current comparable results"
        title="Model Capability Benchmark"
        description="Decision-first analysis across quality, observed latency, known provider cost and dataset-level strengths."
        actions={
          <>
            <div className="segmented">
              {(['all', 'local', 'api'] as const).map((value) => (
                <button
                  type="button"
                  key={value}
                  className={deployment === value ? 'active' : ''}
                  onClick={() => setDeployment(value)}
                >
                  {value === 'all' ? 'All' : value === 'local' ? 'Local' : 'API'}
                </button>
              ))}
            </div>
            <span className="header-chip">MCB v2</span>
            <span className="header-chip current">CURRENT only</span>
          </>
        }
      />

      <section className="kpi-grid">
        <MetricCard
          icon={<Trophy size={19} />}
          label="Best quality"
          model={bestQuality?.model_key ?? 'No result'}
          value={score(bestQuality?.overall_quality_score)}
          caption="Overall benchmark quality · 0–100"
          tone="blue"
          onClick={() => bestQuality && selectModel(bestQuality.model_signature)}
        />
        <MetricCard
          icon={<Laptop size={19} />}
          label="Best local model"
          model={bestLocal?.model_key ?? 'No local result'}
          value={score(bestLocal?.overall_quality_score)}
          caption="Highest quality among CURRENT local models"
          tone="green"
          onClick={() => bestLocal && selectModel(bestLocal.model_signature)}
        />
        <MetricCard
          icon={<Zap size={19} />}
          label="Fastest observed"
          model={fastest?.model_key ?? 'No latency evidence'}
          value={milliseconds(fastest?.latency_p50_ms)}
          caption="Lowest observed P50 · environment-specific"
          tone="amber"
          onClick={() => fastest && selectModel(fastest.model_signature)}
        />
        <MetricCard
          icon={<BadgeDollarSign size={19} />}
          label="Lowest known API cost"
          model={cheapest?.model_key ?? 'No known provider cost'}
          value={usd(cheapest?.provider_cost_per_1k_cases_usd)}
          caption="Known provider cost per 1k benchmark cases"
          tone="violet"
          onClick={() => cheapest && selectModel(cheapest.model_signature)}
        />
      </section>

      <section className="overview-main-grid">
        <QualityLeaderboard
          models={visibleModels}
          selectedModel={selected?.model_signature}
          onSelect={selectModel}
        />
        <TradeoffScatter
          title="Quality × latency"
          description="Observed trade-off. Higher quality and lower P50 are better."
          models={visibleModels}
          xMetric="latency"
          selectedModel={selected?.model_signature}
          onSelect={selectModel}
        />
        <TradeoffScatter
          title="Quality × cost"
          description="Known provider cost only. Local runtime cost is never treated as zero."
          models={visibleModels}
          xMetric="cost"
          selectedModel={selected?.model_signature}
          onSelect={selectModel}
        />
      </section>

      <DatasetPerformanceLandscape
        datasets={decision.dataset_summaries.filter((dataset) =>
          visibleModels.some((model) => model.model_key === dataset.model_key),
        )}
        models={visibleModels}
      />

      <section className="overview-lower-grid">
        <DatasetHeatmap
          datasets={decision.dataset_summaries.filter((dataset) =>
            visibleModels.some((model) => model.model_key === dataset.model_key),
          )}
          models={visibleModels}
        />

        <aside className="analysis-card selected-model-card">
          {selected ? (
            <>
              <div className="selected-model-heading">
                <div className="selected-model-icon"><Cpu size={22} /></div>
                <div>
                  <span>Selected model</span>
                  <h2>{selected.model_key}</h2>
                  <p>
                    {selected.deployment === 'local'
                      ? 'Local execution context and measured efficiency.'
                      : 'API execution context and provider-reported economics.'}
                  </p>
                </div>
                <DeploymentBadge deployment={selected.deployment} />
              </div>

              <dl className="detail-list">
                <div>
                  <dt>Runtime</dt>
                  <dd>{selected.runtime_key || '—'}</dd>
                </div>
                <div>
                  <dt>Hardware</dt>
                  <dd>{selected.deployment === 'local' ? (selected.execution_environment?.cpu_model ?? 'Unavailable') : 'Provider managed / unavailable'}</dd>
                </div>
                <div>
                  <dt>Memory</dt>
                  <dd>{bytes(selected.execution_environment?.total_memory_bytes)}</dd>
                </div>
                <div>
                  <dt>P50 / P95</dt>
                  <dd>
                    {milliseconds(selected.latency_p50_ms)}
                    <span> / </span>
                    {milliseconds(selected.latency_p95_ms)}
                  </dd>
                </div>
                <div>
                  <dt><MemoryStick size={14} /> Peak RSS</dt>
                  <dd>{bytes(selected.resource_summary.process_rss_bytes_peak)}</dd>
                </div>
                <div>
                  <dt><Cpu size={14} /> CPU avg</dt>
                  <dd>{cpu(selected.resource_summary.process_cpu_percent_avg)}</dd>
                </div>
                <div>
                  <dt><Database size={14} /> Provider cost</dt>
                  <dd>
                    {selected.provider_cost_known
                      ? usd(selected.provider_cost_per_1k_cases_usd) + ' / 1k cases'
                      : selected.deployment === 'local'
                        ? 'N/A · local runtime'
                        : 'Unknown'}
                  </dd>
                </div>
              </dl>

              <div className="selected-model-actions">
                <AppLink
                  className="secondary-button"
                  href={'/models/' + encodeURIComponent(selected.model_signature)}
                >
                  Open model
                </AppLink>
                <AppLink
                  className="primary-button"
                  href={'/compare?modelA=' + encodeURIComponent(selected.model_key)}
                >
                  Compare
                </AppLink>
              </div>
            </>
          ) : (
            <div className="empty-visual">Select a model to inspect its execution context.</div>
          )}
        </aside>
      </section>

      <MethodologyAccordion policyLabel={decision.quality_policy.label} />
    </>
  );
}
