import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Cpu,
  GitCompareArrows,
  MemoryStick,
  Share2,
} from 'lucide-react';
import { useState } from 'react';
import { navigate } from '../router';
import type { ReactNode } from 'react';
import {
  modelPayloads,
  overview,
  runPayloads,
} from '../data';
import type {
  CapabilityPayload,
  Disagreement,
  ModelPayload,
  RunPayload,
} from '../types';
import {
  bytes,
  capabilityLabel,
  compactDate,
  cpu,
  milliseconds,
  percent,
  points,
  providerCostCoverage,
  providerCostValue,
  score,
  usd,
} from '../utils';
import {
  DatasetDeltaSlopegraph,
  DatasetHeatmap,
  DeploymentBadge,
  MethodologyAccordion,
  TradeoffScatter,
} from '../components/DecisionComponents';
import {
  ModelArchitectureCard,
  ModelParamBadge,
  ModelParametersComparison,
  ModelQuantBadge,
} from '../components/ModelParameters';
import { AppLink, PageHeader } from '../components/Shell';

const decisionModels = overview.decision?.model_summaries ?? [];
const decisionDatasets = overview.decision?.dataset_summaries ?? [];

function SectionTitle({
  title,
  description,
  aside,
}: {
  title: string;
  description?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {aside}
    </div>
  );
}

export function ModelsPage() {
  const models = [...decisionModels].sort(
    (a, b) => (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1),
  );
  return (
    <>
      <PageHeader
        eyebrow="Current model signatures"
        title="Models"
        description="Rank and shortlist models by quality, coverage, observed latency and known provider cost."
      />
      <section className="analysis-card">
        <SectionTitle
          title="Model leaderboard"
          description="CURRENT decision cohort. Select a model for the full capability and execution profile."
        />
        <div className="premium-table model-table">
          <div className="premium-table-row head">
            <span>Model</span>
            <span>Params</span>
            <span>Quant</span>
            <span>Quality</span>
            <span>Coverage</span>
            <span>P50</span>
            <span>P95</span>
            <span>Cost / 1k</span>
            <span>Environment</span>
          </div>
          {models.length ? models.map((model) => (
            <AppLink
              href={'/models/' + encodeURIComponent(model.model_signature)}
              className="premium-table-row"
              key={model.model_signature}
            >
              <span className="table-model">
                <strong>{model.model_key}</strong>
                <DeploymentBadge deployment={model.deployment} />
              </span>
              <span>
                <ModelParamBadge parameters_b={model.parameters_b} deployment={model.deployment} />
              </span>
              <span>
                <ModelQuantBadge quantization={model.quantization} deployment={model.deployment} />
              </span>
              <strong>{score(model.overall_quality_score)}</strong>
              <span>
                {model.quality_coverage_capabilities}/{model.quality_total_capabilities}
                {!model.quality_coverage_complete ? ' · partial' : ''}
              </span>
              <span>{milliseconds(model.latency_p50_ms)}</span>
              <span>{milliseconds(model.latency_p95_ms)}</span>
              <span>
                {providerCostValue(
                  model.provider_cost_status,
                  model.provider_cost_per_1k_cases_usd,
                )}
                {model.provider_cost_known ? ' / 1k' : ''}
                <small className="table-cost-coverage">
                  {providerCostCoverage(
                    model.provider_cost_status,
                    model.provider_cost_priced_cases,
                    model.provider_cost_total_cases,
                    model.provider_cost_coverage_rate,
                  )}
                </small>
              </span>
              <span>{model.execution_environment?.cpu_model ?? model.runtime_key}</span>
            </AppLink>
          )) : (
            <div className="empty-visual">Project real runs to populate decision summaries.</div>
          )}
        </div>
      </section>
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label} />
    </>
  );
}

export function ModelPage({ signature }: { signature: string }) {
  const payload = Object.values(modelPayloads).find(
    (item) => item.model_signature === signature,
  ) as ModelPayload | undefined;
  const summary =
    payload?.decision_summary ??
    decisionModels.find((item) => item.model_signature === signature) ??
    null;
  const model = payload?.model ??
    overview.models.find((item) => item.model_signature === signature) ??
    null;
  const currentCells = payload?.current_cells ??
    overview.cells.filter((item) => item.model_signature === signature);
  const history = payload?.history ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Model profile"
        title={model?.model_key ?? summary?.model_key ?? 'Model'}
        description={model?.model_id ?? 'CURRENT benchmark evidence and execution context.'}
        actions={
          <>
            <ModelParamBadge parameters_b={summary?.parameters_b ?? model?.parameters_b} deployment={summary?.deployment ?? model?.deployment} />
            <ModelQuantBadge quantization={summary?.quantization ?? model?.quantization} deployment={summary?.deployment ?? model?.deployment} />
            <DeploymentBadge deployment={model?.deployment ?? summary?.deployment ?? 'unknown'} />
            <span className="header-chip current">CURRENT</span>
          </>
        }
      />

      <section className="model-kpi-grid">
        <div className="mini-kpi">
          <span>Overall quality</span><strong>{score(summary?.overall_quality_score)}</strong>
          <small>/100 · {summary?.quality_coverage_complete ? 'complete coverage' : 'partial coverage'}</small>
        </div>
        <div className="mini-kpi">
          <span>Datasets covered</span>
          <strong>{summary ? summary.quality_coverage_datasets + '/' + summary.quality_total_datasets : '—'}</strong>
          <small>selected CURRENT cohort</small>
        </div>
        <div className="mini-kpi">
          <span>P50 latency</span><strong>{milliseconds(summary?.latency_p50_ms)}</strong>
          <small>observed execution latency</small>
        </div>
        <div className="mini-kpi">
          <span>Peak RSS</span><strong>{bytes(summary?.resource_summary.process_rss_bytes_peak)}</strong>
          <small>runtime telemetry when available</small>
        </div>
        <div className="mini-kpi">
          <span>Provider cost</span>
          <strong>{providerCostValue(
            summary?.provider_cost_status,
            summary?.provider_cost_per_1k_cases_usd,
          )}</strong>
          <small>
            {summary
              ? providerCostCoverage(
                  summary.provider_cost_status,
                  summary.provider_cost_priced_cases,
                  summary.provider_cost_total_cases,
                  summary.provider_cost_coverage_rate,
                )
              : 'pricing unavailable'}
          </small>
        </div>
      </section>

      <section className="analysis-card model-config-section">
        <SectionTitle
          title="Model Parameters & Configuration"
          description="Architecture specification, parameter scale, quantization format, and sampling parameters used during benchmark evaluation."
        />
        {(summary || model) ? (
          <ModelArchitectureCard model={(summary ?? model)!} />
        ) : null}
      </section>

      <section className="two-panel-grid model-primary-grid">
        <div className="analysis-card">
          <SectionTitle
            title="Capability performance"
            description="Task-level primary metrics remain authoritative."
          />
          <div className="capability-bars">
            {currentCells.map((cell) => {
              const value = (cell.primary_value ?? 0) * 100;
              return (
                <AppLink
                  key={cell.capability_id}
                  href={'/capabilities/' + encodeURIComponent(cell.capability_id)}
                  className="capability-bar-row"
                >
                  <span>{capabilityLabel(cell.capability_id)}</span>
                  <div><i style={{ width: value + '%' }} /></div>
                  <strong>{value.toFixed(1)}</strong>
                </AppLink>
              );
            })}
          </div>
        </div>

        <div className="analysis-card">
          <SectionTitle
            title="Execution environment"
            description="Human-readable runtime identity for this result."
          />
          <dl className="detail-list">
            <div><dt>Deployment</dt><dd>{summary?.deployment ?? model?.deployment ?? '—'}</dd></div>
            <div><dt>Runtime</dt><dd>{summary?.runtime_key ?? model?.runtime_key ?? '—'}</dd></div>
            <div><dt>Hardware</dt><dd>{summary?.deployment === 'local' ? (summary.execution_environment?.cpu_model ?? 'Unavailable') : 'Provider managed / unavailable'}</dd></div>
            <div><dt>Architecture</dt><dd>{summary?.execution_environment?.machine ?? '—'}</dd></div>
            <div><dt>Operating system</dt><dd>{summary?.execution_environment?.system ?? '—'} {summary?.execution_environment?.release ?? ''}</dd></div>
            <div><dt>Memory</dt><dd>{bytes(summary?.execution_environment?.total_memory_bytes)}</dd></div>
            <div>
              <dt>Pricing snapshot</dt>
              <dd>
                {summary?.provider_cost_pricing
                  ? [
                      summary.provider_cost_pricing.as_of
                        ? 'as of ' + summary.provider_cost_pricing.as_of
                        : null,
                      summary.provider_cost_pricing.processing,
                    ].filter(Boolean).join(' · ')
                  : summary?.deployment === 'local'
                    ? 'Not applicable'
                    : 'No frozen price match'}
              </dd>
            </div>
            <div><dt>Execution lineages</dt><dd>{summary?.execution_count ?? '—'}</dd></div>
          </dl>
        </div>
      </section>

      <section className="two-panel-grid">
        <div className="analysis-card">
          <SectionTitle
            title="Comparable history"
            description="History remains separated when benchmark lineage changes."
          />
          {history.length ? (
            <div className="history-list">
              {history.map((row) => (
                <div key={row.run_id + row.capability_id}>
                  <span>{compactDate(row.completed_at_utc)}</span>
                  <strong>{capabilityLabel(row.capability_id)}</strong>
                  <b>{percent(row.primary_value)}</b>
                  <em className={'history-state ' + row.result_state.toLowerCase()}>
                    {row.result_state}
                  </em>
                </div>
              ))}
            </div>
          ) : <div className="empty-visual">No comparable history projected yet.</div>}
        </div>

        <div className="analysis-card">
          <SectionTitle
            title="Resource telemetry"
            description="Measured runtime evidence; unavailable fields remain explicit."
          />
          <div className="telemetry-grid">
            <div><Cpu size={16}/><span>CPU avg</span><strong>{cpu(summary?.resource_summary.process_cpu_percent_avg)}</strong></div>
            <div><MemoryStick size={16}/><span>RSS peak</span><strong>{bytes(summary?.resource_summary.process_rss_bytes_peak)}</strong></div>
            <div><Activity size={16}/><span>P50</span><strong>{milliseconds(summary?.latency_p50_ms)}</strong></div>
            <div><Activity size={16}/><span>P95</span><strong>{milliseconds(summary?.latency_p95_ms)}</strong></div>
          </div>
        </div>
      </section>

      <section className="two-panel-grid">
        <div className="analysis-card">
          <SectionTitle title="Dataset profile" description="Strongest and weakest CURRENT dataset results." />
          <div className="dataset-profile">
            {decisionDatasets
              .filter((item) => item.model_signature === signature)
              .sort((a, b) => (b.normalized_quality_score ?? -1) - (a.normalized_quality_score ?? -1))
              .map((item) => (
                <AppLink href={'/datasets/' + encodeURIComponent(item.dataset_id)} key={item.capability_id + item.dataset_id}>
                  <span>{item.dataset_id}</span><strong>{score(item.normalized_quality_score)}</strong>
                </AppLink>
              ))}
          </div>
        </div>
        <div className="analysis-card">
          <SectionTitle title="Representative failures" description="Failure cases stay behind the aggregate decision layer." />
          <p className="muted-copy">
            Open a capability disagreement explorer to inspect expected output,
            prediction and raw evidence without loading the full corpus here.
          </p>
          {currentCells[0] ? (
            <AppLink className="secondary-button" href={'/capabilities/' + currentCells[0].capability_id + '/disagreements'}>
              View disagreements
            </AppLink>
          ) : null}
        </div>
      </section>
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label} />
    </>
  );
}

export function CapabilityPage({ payload }: { payload: CapabilityPayload }) {
  const capabilityModels = decisionModels.filter((model) =>
    payload.cells.some((cell) => cell.model_signature === model.model_signature),
  );
  const summaries = payload.decision?.capability_summaries ?? [];
  const datasets = payload.decision?.dataset_summaries ?? [];
  const capabilityTradeoffModels = capabilityModels.map((model) => {
    const summary = summaries.find((item) => item.model_signature === model.model_signature);
    return summary
      ? {
          ...model,
          overall_quality_score: summary.normalized_quality_score,
          latency_p50_ms: summary.latency_p50_ms,
          latency_p95_ms: summary.latency_p95_ms,
          latency_mean_ms: summary.latency_mean_ms,
          provider_cost_status: summary.provider_cost_status,
          provider_cost_known: summary.provider_cost_known,
          provider_cost_priced_cases: summary.provider_cost_priced_cases,
          provider_cost_total_cases: summary.provider_cost_total_cases,
          provider_cost_coverage_rate: summary.provider_cost_coverage_rate,
          provider_cost_pricing: summary.provider_cost_pricing,
          provider_cost_observed_total_usd: summary.provider_cost_observed_total_usd,
          provider_cost_total_usd: summary.provider_cost_total_usd,
          provider_cost_per_case_usd: summary.provider_cost_per_case_usd,
          provider_cost_per_1k_cases_usd: summary.provider_cost_per_1k_cases_usd,
          failure_count: summary.failure_count,
          failure_rate: summary.failure_rate,
          observed_quality_latency_pareto:
            summary.observed_quality_latency_pareto,
          known_provider_cost_quality_pareto:
            summary.known_provider_cost_quality_pareto,
        }
      : model;
  });
  const families = Array.from(new Set(payload.family_breakdown.map((row) => row.family)));
  const comparison = payload.comparison;

  return (
    <>
      <PageHeader
        eyebrow="Capability detail"
        title={capabilityLabel(payload.capability_id)}
        description="Understand the aggregate result through datasets, controlled failure families and paired same-case evidence."
        actions={
          <AppLink
            href={'/capabilities/' + payload.capability_id + '/disagreements'}
            className="primary-button"
          >
            Explore disagreements
          </AppLink>
        }
      />

      <section className="capability-hero-grid">
        {summaries.length ? summaries.map((item) => (
          <div className="model-score-card" key={item.model_signature}>
            <div>
              <strong>{item.model_key}</strong>
              <DeploymentBadge deployment={capabilityModels.find((m) => m.model_key === item.model_key)?.deployment ?? 'unknown'} />
            </div>
            <b>{score(item.normalized_quality_score)}</b>
            <span>{item.primary_metric} · n={item.sample_count}</span>
          </div>
        )) : payload.cells.map((cell) => (
          <div className="model-score-card" key={cell.model_signature}>
            <strong>{cell.model_key}</strong>
            <b>{percent(cell.primary_value)}</b>
            <span>{cell.primary_metric} · n={cell.sample_count}</span>
          </div>
        ))}
        {comparison ? (
          <div className="model-score-card delta">
            <strong>Paired delta</strong>
            <b>{points(comparison.delta_b_minus_a)}</b>
            <span>95% CI {points(comparison.ci95_low)} → {points(comparison.ci95_high)} · n={comparison.paired_count}</span>
          </div>
        ) : null}
      </section>

      <section className="capability-analysis-grid">
        <DatasetHeatmap datasets={datasets} models={capabilityModels} />
        <TradeoffScatter
          title="Quality × latency"
          description="Observed capability-level context."
          models={capabilityTradeoffModels}
          xMetric="latency"
        />
        <TradeoffScatter
          title="Quality × cost"
          description="Known provider cost only."
          models={capabilityTradeoffModels}
          xMetric="cost"
        />
      </section>

      <section className="two-panel-grid">
        <div className="analysis-card">
          <SectionTitle title="Failure-family breakdown" description="Where the capability-level quality gap comes from." />
          <div className="family-breakdown">
            {families.map((family) => (
              <div className="family-group" key={family}>
                <strong>{family}</strong>
                {payload.cells.map((cell, modelIndex) => {
                  const row = payload.family_breakdown.find(
                    (item) => item.family === family && item.model_key === cell.model_key,
                  );
                  return (
                    <div key={cell.model_key}>
                      <span>{cell.model_key}</span>
                      <i>
                        <b
                          className={'family-model-' + (modelIndex % 4)}
                          style={{ width: ((row?.value ?? 0) * 100) + '%' }}
                        />
                      </i>
                      <em>{percent(row?.value)}</em>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        <div className="analysis-card">
          <SectionTitle title="Disagreement preview" description="Paired valid evaluations only; pipeline failures stay separate." />
          <div className="disagreement-preview">
            {payload.disagreements.slice(0, 5).map((item) => (
              <div key={item.sample_id}>
                <span><strong>{item.sample_id}</strong><small>{item.family} · {item.difficulty}</small></span>
                <OutcomeBadge outcome={item.outcome} />
              </div>
            ))}
          </div>
          <AppLink className="secondary-button wide" href={'/capabilities/' + payload.capability_id + '/disagreements'}>
            Open disagreement explorer
          </AppLink>
        </div>
      </section>
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label} />
    </>
  );
}

export function DatasetPage({ datasetId }: { datasetId: string }) {
  const rows = decisionDatasets.filter((item) => item.dataset_id === datasetId);
  const models = decisionModels.filter((model) =>
    rows.some((row) => row.model_signature === model.model_signature),
  );
  const ranked = [...rows].sort(
    (a, b) => (b.normalized_quality_score ?? -1) - (a.normalized_quality_score ?? -1),
  );
  const datasetTradeoffModels = models.map((model) => {
    const row = rows.find((item) => item.model_signature === model.model_signature);
    return row
      ? {
          ...model,
          overall_quality_score: row.normalized_quality_score,
          latency_p50_ms: row.latency_p50_ms,
          latency_p95_ms: row.latency_p95_ms,
          latency_mean_ms: row.latency_mean_ms,
          provider_cost_status: row.provider_cost_status,
          provider_cost_known: row.provider_cost_known,
          provider_cost_priced_cases: row.provider_cost_priced_cases,
          provider_cost_total_cases: row.provider_cost_total_cases,
          provider_cost_coverage_rate: row.provider_cost_coverage_rate,
          provider_cost_pricing: row.provider_cost_pricing,
          provider_cost_observed_total_usd: row.provider_cost_observed_total_usd,
          provider_cost_total_usd: row.provider_cost_total_usd,
          provider_cost_per_case_usd: row.provider_cost_per_case_usd,
          provider_cost_per_1k_cases_usd: row.provider_cost_per_1k_cases_usd,
          failure_count: row.failure_count,
          failure_rate: row.failure_rate,
          observed_quality_latency_pareto: row.observed_quality_latency_pareto,
          known_provider_cost_quality_pareto:
            row.known_provider_cost_quality_pareto,
        }
      : model;
  });
  return (
    <>
      <PageHeader
        eyebrow="Dataset detail"
        title={datasetId}
        description="Dataset-level ranking and execution trade-offs behind the capability result."
      />
      <section className="dataset-detail-grid">
        <div className="analysis-card">
          <SectionTitle title="Dataset ranking" description="Primary metric normalized to the decision scale." />
          <div className="dataset-ranking">
            {ranked.map((row, index) => (
              <div key={row.model_signature}>
                <span className="rank">{index + 1}</span>
                <strong>{row.model_key}</strong>
                <span>{score(row.normalized_quality_score)}</span>
                <small>
                  {milliseconds(row.latency_p50_ms)} · {providerCostValue(
                    row.provider_cost_status,
                    row.provider_cost_per_1k_cases_usd,
                  )}
                  {row.provider_cost_known ? '/1k' : ''}
                  {row.provider_cost_status === 'partial'
                    ? ' · ' + Math.round((row.provider_cost_coverage_rate ?? 0) * 100) + '% priced'
                    : ''}
                </small>
              </div>
            ))}
          </div>
        </div>
        <div className="analysis-card">
          <SectionTitle title="Context" description="Dataset evidence remains tied to its parent capability." />
          <dl className="detail-list">
            <div><dt>Capability</dt><dd>{rows[0] ? capabilityLabel(rows[0].capability_id) : '—'}</dd></div>
            <div><dt>Primary metric</dt><dd>{rows[0]?.primary_metric ?? '—'}</dd></div>
            <div><dt>Samples / model</dt><dd>{rows[0]?.sample_count ?? '—'}</dd></div>
          </dl>
        </div>
      </section>
      <section className="two-panel-grid">
        <TradeoffScatter
          title="Quality × latency"
          description="Observed trade-off for this dataset only."
          models={datasetTradeoffModels}
          xMetric="latency"
        />
        <TradeoffScatter
          title="Quality × cost"
          description="Known provider cost for this dataset only."
          models={datasetTradeoffModels}
          xMetric="cost"
        />
      </section>
      <section className="analysis-card">
        <SectionTitle title="Models on this dataset" description="Quality, observed latency and known provider cost." />
        <DatasetHeatmap datasets={rows} models={models} />
      </section>
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label} />
    </>
  );
}

function compareHref(modelA: string, modelB: string): string {
  const params = new URLSearchParams({ modelA, modelB });
  return '/compare?' + params.toString();
}

function queryParam(name: string): string | null {
  const direct = new URLSearchParams(window.location.search).get(name);
  if (direct) return direct;
  if (window.location.hash.includes('?')) {
    return new URLSearchParams(window.location.hash.split('?')[1]).get(name);
  }
  return null;
}

export function ComparePage() {
  const models = [...decisionModels].sort(
    (a, b) => (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1),
  );
  const initialA = queryParam('modelA') ?? models[0]?.model_key ?? '';
  const initialB =
    queryParam('modelB') ??
    models.find(
      (model) =>
        model.model_key !== initialA && model.deployment === 'local',
    )?.model_key ??
    models.find((model) => model.model_key !== initialA)?.model_key ??
    '';
  const [modelAKey, setModelAKey] = useState(initialA);
  const [modelBKey, setModelBKey] = useState(initialB);
  const modelA = models.find((model) => model.model_key === modelAKey) ?? models[0];
  const modelB =
    models.find((model) => model.model_key === modelBKey) ??
    models.find((model) => model.model_key !== modelA?.model_key);
  const datasetsA = decisionDatasets.filter((row) => row.model_key === modelA?.model_key);
  const datasetsB = new Map(
    decisionDatasets
      .filter((row) => row.model_key === modelB?.model_key)
      .map((row) => [row.capability_id + '::' + row.dataset_id, row]),
  );

  const qualityDelta =
    modelA?.overall_quality_score != null && modelB?.overall_quality_score != null
      ? modelA.overall_quality_score - modelB.overall_quality_score
      : null;

  return (
    <>
      <PageHeader
        eyebrow="Decision workspace"
        title="Compare models"
        description="Compare finalists across quality, dataset performance, observed latency, cost and execution semantics."
        actions={
          <div className="compare-selectors">
            <select
              value={modelA?.model_key ?? ''}
              onChange={(event) => {
                const next = event.target.value;
                setModelAKey(next);
                navigate(compareHref(next, modelB?.model_key ?? ''));
              }}
            >
              {models.map((model) => <option key={model.model_key}>{model.model_key}</option>)}
            </select>
            <span>vs</span>
            <select
              value={modelB?.model_key ?? ''}
              onChange={(event) => {
                const next = event.target.value;
                setModelBKey(next);
                navigate(compareHref(modelA?.model_key ?? '', next));
              }}
            >
              {models.filter((model) => model.model_key !== modelA?.model_key).map((model) => (
                <option key={model.model_key}>{model.model_key}</option>
              ))}
            </select>
          </div>
        }
      />
      {modelA && modelB ? (
        <>
          <section className="compare-hero-grid">
            {[modelA, modelB].map((model, index) => (
              <div className="compare-model-card" key={model.model_signature}>
                <div><strong>{model.model_key}</strong><DeploymentBadge deployment={model.deployment}/></div>
                <span>{index === 0 ? 'Model A' : 'Model B'}</span>
                <div className="compare-mini-grid">
                  <div><small>Quality</small><b>{score(model.overall_quality_score)}</b></div>
                  <div><small>P50</small><b>{milliseconds(model.latency_p50_ms)}</b></div>
                  <div>
                    <small>Cost / 1k</small>
                    <b>{providerCostValue(
                      model.provider_cost_status,
                      model.provider_cost_per_1k_cases_usd,
                    )}</b>
                    <em className={'cost-status ' + model.provider_cost_status}>
                      {model.provider_cost_status === 'partial'
                        ? Math.round((model.provider_cost_coverage_rate ?? 0) * 100) + '% priced'
                        : model.provider_cost_status === 'complete'
                          ? 'complete'
                          : model.provider_cost_status === 'local_not_applicable'
                            ? 'local'
                            : 'unavailable'}
                    </em>
                  </div>
                  <div><small>Failures</small><b>{percent(model.failure_rate)}</b></div>
                </div>
              </div>
            ))}
            <div className="compare-delta-card">
              <GitCompareArrows size={20}/>
              <strong>Delta A − B</strong>
              <b>{qualityDelta == null ? '—' : (qualityDelta >= 0 ? '+' : '') + qualityDelta.toFixed(1)}</b>
              <span>quality points</span>
              <small>
                Latency {modelA.latency_p50_ms != null && modelB.latency_p50_ms != null
                  ? milliseconds(modelA.latency_p50_ms - modelB.latency_p50_ms)
                  : '—'}
              </small>
            </div>
          </section>

          <section className="compare-workspace-grid">
            <div className="analysis-card">
              <SectionTitle title="Side-by-side metrics" description="Bars are normalized within each metric only." />
              <ComparisonMetric label="Quality" a={modelA.overall_quality_score} b={modelB.overall_quality_score} format={score}/>
              <ComparisonMetric label="P50 latency" a={modelA.latency_p50_ms} b={modelB.latency_p50_ms} format={milliseconds} lowerBetter/>
              <ComparisonMetric label="P95 latency" a={modelA.latency_p95_ms} b={modelB.latency_p95_ms} format={milliseconds} lowerBetter/>
              <ComparisonMetric label="Provider cost / 1k" a={modelA.provider_cost_per_1k_cases_usd} b={modelB.provider_cost_per_1k_cases_usd} format={usd} lowerBetter/>
              <ComparisonMetric label="Failure rate" a={modelA.failure_rate} b={modelB.failure_rate} format={percent} lowerBetter/>
            </div>
            <div className="tradeoff-pair">
              <TradeoffScatter title="Quality × latency" description="Selected models in the wider field." models={models} xMetric="latency" selectedModel={modelA.model_signature}/>
              <TradeoffScatter title="Quality × cost" description="Known provider cost only." models={models} xMetric="cost" selectedModel={modelA.model_signature}/>
            </div>
          </section>

          <DatasetDeltaSlopegraph
            datasets={decisionDatasets}
            modelA={modelA}
            modelB={modelB}
          />

          <section className="analysis-card">
            <SectionTitle
              title="Parameter & Configuration Comparison"
              description="Side-by-side comparison of architecture scale, quantization, and generation parameters."
            />
            <ModelParametersComparison modelA={modelA} modelB={modelB} />
          </section>

          <section className="two-panel-grid">
            <div className="analysis-card">
              <SectionTitle title="Dataset delta table" description="Exact values behind the slopegraph." />
              <div className="dataset-delta-table">
                {datasetsA.map((a) => {
                  const b = datasetsB.get(a.capability_id + '::' + a.dataset_id);
                  const delta =
                    a.normalized_quality_score != null && b?.normalized_quality_score != null
                      ? a.normalized_quality_score - b.normalized_quality_score
                      : null;
                  return (
                    <div key={a.capability_id + a.dataset_id}>
                      <span><strong>{a.dataset_id}</strong><small>{capabilityLabel(a.capability_id)}</small></span>
                      <b>{score(a.normalized_quality_score)}</b>
                      <b>{score(b?.normalized_quality_score)}</b>
                      <em className={delta != null && delta < 0 ? 'negative' : 'positive'}>
                        {delta == null ? '—' : (delta > 0 ? '+' : '') + delta.toFixed(1)}
                      </em>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="analysis-card">
              <SectionTitle
                title="Efficiency semantics"
                description="Quality comparability is separate from runtime efficiency semantics."
                aside={<span className="warning-chip"><AlertTriangle size={14}/> observed trade-off</span>}
              />
              <div className="semantics-grid">
                <div><CheckCircle2 size={19}/><strong>Quality comparable</strong><p>The decision cohort keeps a common benchmark lineage per capability.</p></div>
                <div><AlertTriangle size={19}/><strong>Efficiency environment-specific</strong><p>Latency across different runtimes is descriptive unless execution semantics match.</p></div>
              </div>
            </div>
          </section>
        </>
      ) : <div className="analysis-card empty-visual">At least two decision summaries are required.</div>}
      <MethodologyAccordion policyLabel={overview.decision?.quality_policy.label} />
    </>
  );
}

function ComparisonMetric({
  label,
  a,
  b,
  format,
}: {
  label: string;
  a: number | null | undefined;
  b: number | null | undefined;
  format: (value: number | null | undefined) => string;
  lowerBetter?: boolean;
}) {
  const max = Math.max(Number(a ?? 0), Number(b ?? 0), 0.0001);
  return (
    <div className="comparison-metric">
      <strong>{label}</strong>
      <div><i style={{ width: (Number(a ?? 0) / max) * 100 + '%' }}/><span>{format(a)}</span></div>
      <div><i className="b" style={{ width: (Number(b ?? 0) / max) * 100 + '%' }}/><span>{format(b)}</span></div>
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome: Disagreement['outcome'] }) {
  const labels: Record<Disagreement['outcome'], string> = {
    both_correct: 'Both correct',
    a_only_correct: 'A only',
    b_only_correct: 'B only',
    both_wrong: 'Both wrong',
    pipeline_failure: 'Pipeline failure',
  };
  return <span className={'outcome ' + outcome}>{labels[outcome]}</span>;
}

export function DisagreementsPage({ payload }: { payload: CapabilityPayload }) {
  const [filter, setFilter] = useState<Disagreement['outcome'] | 'all'>('all');
  const [selectedId, setSelectedId] = useState(payload.disagreements[0]?.sample_id ?? '');
  const items = payload.disagreements.filter(
    (item) => filter === 'all' || item.outcome === filter,
  );
  const selected = items.find((item) => item.sample_id === selectedId) ?? items[0];

  return (
    <>
      <PageHeader
        eyebrow="Failure analysis"
        title="Disagreement explorer"
        description={'Paired evidence for ' + capabilityLabel(payload.capability_id) + '. Pipeline failures remain separate from quality disagreements.'}
        actions={<AppLink className="secondary-button" href={'/capabilities/' + payload.capability_id}>Back to capability</AppLink>}
      />
      <div className="filter-row">
        {(['all', 'b_only_correct', 'a_only_correct', 'both_wrong', 'pipeline_failure'] as const).map((value) => (
          <button key={value} type="button" className={filter === value ? 'filter active' : 'filter'} onClick={() => setFilter(value)}>
            {value.replaceAll('_', ' ')}
          </button>
        ))}
      </div>
      <section className="disagreement-layout">
        <div className="analysis-card case-list">
          {items.map((item) => (
            <button type="button" key={item.sample_id} onClick={() => setSelectedId(item.sample_id)} className={selected?.sample_id === item.sample_id ? 'case-item selected' : 'case-item'}>
              <span><strong>{item.sample_id}</strong><small>{item.dataset_id} · {item.family}</small></span>
              <OutcomeBadge outcome={item.outcome}/>
            </button>
          ))}
        </div>
        <div className="analysis-card case-detail">
          {selected ? (
            <>
              <SectionTitle title={selected.sample_id} description={[selected.family, selected.difficulty, selected.challenge_type].filter(Boolean).join(' · ')} aside={<OutcomeBadge outcome={selected.outcome}/>}/>
              <div className="case-columns">
                <article><span>Expected</span><pre>{JSON.stringify(selected.expected ?? {}, null, 2)}</pre></article>
                <article><span>{selected.model_a}</span><pre>{JSON.stringify(selected.prediction_a ?? {}, null, 2)}</pre></article>
                <article><span>{selected.model_b}</span><pre>{JSON.stringify(selected.prediction_b ?? {}, null, 2)}</pre></article>
              </div>
            </>
          ) : <div className="empty-visual">No disagreements match this filter.</div>}
        </div>
      </section>
    </>
  );
}

export function RunsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Operational observability"
        title="Runs"
        description="Audit completed, historical and partial executions without changing CURRENT decision results."
      />
      <section className="analysis-card">
        <div className="premium-table runs-table">
          <div className="premium-table-row head"><span>Run</span><span>Status</span><span>Profile</span><span>Completed</span><span>Commit</span></div>
          {overview.runs.map((run) => {
            const runId = String(run.run_id ?? '');
            return (
              <AppLink key={runId} href={'/runs/' + encodeURIComponent(runId)} className="premium-table-row">
                <strong>{runId}</strong>
                <span className={'run-status ' + String(run.status ?? '').toLowerCase()}>{String(run.status ?? 'UNKNOWN')}</span>
                <span>{String(run.profile ?? '—')}</span>
                <span>{String(run.completed_at_utc ?? '—')}</span>
                <span>{String(run.git_commit ?? '—')}</span>
              </AppLink>
            );
          })}
        </div>
      </section>
    </>
  );
}

export function RunPage({ runId }: { runId: string }) {
  const payload = runPayloads[runId] as RunPayload | undefined;
  const summary = payload?.run ?? overview.runs.find((run) => String(run.run_id) === runId);
  const failures = payload?.failure_summary.reduce((total, item) => total + item.count, 0) ?? 0;
  return (
    <>
      <PageHeader
        eyebrow="Run audit"
        title={runId}
        description="Operational lifecycle, failures and resource evidence for one immutable execution."
        actions={<span className="header-chip">{String(summary?.status ?? 'UNKNOWN')}</span>}
      />
      <section className="run-kpi-grid">
        <div className="mini-kpi"><span>Models</span><strong>{payload?.models.length ?? '—'}</strong><small>execution identities</small></div>
        <div className="mini-kpi"><span>Cells</span><strong>{payload?.cells.length ?? '—'}</strong><small>model × capability</small></div>
        <div className="mini-kpi"><span>Failures</span><strong>{failures}</strong><small>typed lifecycle errors</small></div>
        <div className="mini-kpi"><span>Profile</span><strong>{String(summary?.profile ?? '—')}</strong><small>benchmark tier</small></div>
      </section>
      <section className="two-panel-grid">
        <div className="analysis-card">
          <SectionTitle title="Failures" description="Grouped before raw lifecycle events." />
          {payload?.failure_summary.length ? (
            <div className="failure-list">
              {payload.failure_summary.map((failure) => (
                <div key={failure.event_type + failure.error_type}>
                  <strong>{failure.event_type}</strong><span>{failure.error_type}</span><b>{failure.count}</b>
                </div>
              ))}
            </div>
          ) : <div className="empty-success"><CheckCircle2 size={18}/> No lifecycle failures recorded.</div>}
        </div>
        <div className="analysis-card">
          <SectionTitle title="Resource summary" description="Measured evidence by model/capability." />
          <div className="resource-list">
            {payload?.resources.map((resource) => (
              <div key={resource.model_key + resource.capability_id}>
                <span><strong>{resource.model_key}</strong><small>{capabilityLabel(resource.capability_id)}</small></span>
                <b>{cpu(resource.process_cpu_percent_avg)}</b>
                <b>{bytes(resource.process_rss_bytes_peak)}</b>
                <em>n={resource.sample_count}</em>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="analysis-card">
        <details className="timeline-details">
          <summary>Lifecycle timeline · {payload?.timeline.length ?? 0} events</summary>
          <div className="run-timeline">
            {payload?.timeline.map((event, index) => (
              <div key={event.timestamp_utc + event.event_type + index}>
                <span>{event.timestamp_utc}</span><i/><strong>{event.event_type}</strong>
                <small>{[event.model_key, event.capability_id].filter(Boolean).join(' · ')}</small>
              </div>
            ))}
          </div>
        </details>
      </section>
    </>
  );
}

export function SharePage() {
  return (
    <>
      <PageHeader
        eyebrow="Immutable share snapshot"
        title="Share results"
        description="Public assets are rendered from frozen benchmark snapshots, never from live dashboard state."
        actions={<span className="header-chip"><Share2 size={14}/> snapshot-only</span>}
      />
      <section className="share-page-grid">
        <div className="analysis-card">
          <SectionTitle title="Templates" description="Dedicated social compositions using the same metric semantics." />
          <div className="template-list">
            <button type="button" className="active">Result comparison</button>
            <button type="button">Capability deep dive</button>
            <button type="button">Efficiency comparison</button>
            <button type="button">Methodology</button>
          </div>
        </div>
        <div className="share-preview">
          <span>MCB · Model Capability Benchmark</span>
          <h2>Clearer evidence for model selection.</h2>
          <p>Quality, latency, cost and provenance in one immutable benchmark story.</p>
          <div className="share-preview-stat"><BarChart3/><strong>Decision-ready</strong><small>snapshot-backed evidence</small></div>
        </div>
      </section>
    </>
  );
}

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <PageHeader title={title} eyebrow="MCB" description="This analytical surface is not available for the selected evidence." />
      <section className="analysis-card empty-visual">No projected data available.</section>
    </>
  );
}
