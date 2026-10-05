export interface DashboardModel {
  model_key: string;
  model_id: string;
  effective_model_id: string;
  model_signature: string;
  runtime_key: string;
  provider_key: string;
  deployment: string;
}

export interface ExecutionEnvironment {
  run_id?: string;
  execution_signature?: string;
  system: string | null;
  release: string | null;
  machine: string | null;
  cpu_model: string | null;
  total_memory_bytes: number | null;
}

export interface ResourceSummary {
  source: string;
  scope: string;
  sample_count: number;
  sample_interval_ms: number | null;
  process_cpu_percent_avg: number | null;
  process_rss_bytes_avg: number | null;
  process_rss_bytes_peak: number | null;
  system_available_memory_bytes_min: number | null;
  accelerator_memory_bytes_peak: number | null;
  sampling_error_count: number;
}

export interface CapabilityCell {
  run_id: string;
  model_key: string;
  model_signature: string;
  benchmark_signature: string;
  execution_signature: string;
  capability_id: string;
  task_id: string;
  profile: string;
  sample_count: number;
  failure_count: number;
  primary_metric: string;
  primary_value: number | null;
  comparison_metric?: string | null;
  practical_delta?: number | null;
  completed_at_utc: string;
  git_commit?: string | null;
  model_id?: string;
  effective_model_id?: string;
  runtime_key?: string;
  provider_key?: string;
  deployment?: string;
  resource_summary?: ResourceSummary | null;
}

export interface QualityPolicy {
  quality_policy_id: string;
  label: string;
  aggregation: string;
  coverage_requirement: string;
  normalization: string;
}

export interface DecisionModelSummary extends DashboardModel {
  quality_policy_id: string;
  overall_quality_score: number | null;
  quality_coverage_capabilities: number;
  quality_total_capabilities: number;
  quality_coverage_datasets: number;
  quality_total_datasets: number;
  quality_coverage_complete: boolean;
  observed_case_count: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_mean_ms: number | null;
  provider_cost_status: 'complete' | 'partial' | 'unavailable' | 'local_not_applicable';
  provider_cost_known: boolean;
  provider_cost_priced_cases: number;
  provider_cost_total_cases: number;
  provider_cost_coverage_rate: number | null;
  provider_cost_total_usd: number | null;
  provider_cost_per_case_usd: number | null;
  provider_cost_per_1k_cases_usd: number | null;
  input_tokens_total: number | null;
  output_tokens_total: number | null;
  failure_count: number;
  failure_rate: number | null;
  execution_count: number;
  execution_environment: ExecutionEnvironment | null;
  resource_summary: {
    process_cpu_percent_avg: number | null;
    process_rss_bytes_peak: number | null;
  };
  latest_completed_at_utc: string | null;
  current_run_ids: string[];
  observed_quality_latency_pareto: boolean;
  known_provider_cost_quality_pareto: boolean;
}

export interface DecisionCapabilitySummary {
  run_id: string;
  model_key: string;
  model_signature: string;
  capability_id: string;
  benchmark_signature: string;
  execution_signature: string;
  primary_metric: string;
  primary_value: number | null;
  normalized_quality_score: number | null;
  sample_count: number;
  failure_count: number;
  observed_case_count: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_mean_ms: number | null;
  provider_cost_status: 'complete' | 'partial' | 'unavailable' | 'local_not_applicable';
  provider_cost_known: boolean;
  provider_cost_priced_cases: number;
  provider_cost_total_cases: number;
  provider_cost_coverage_rate: number | null;
  provider_cost_total_usd: number | null;
  provider_cost_per_case_usd: number | null;
  provider_cost_per_1k_cases_usd: number | null;
  input_tokens_total: number | null;
  output_tokens_total: number | null;
  failure_rate: number | null;
  observed_quality_latency_pareto: boolean;
  known_provider_cost_quality_pareto: boolean;
}

export interface DecisionDatasetSummary {
  model_key: string;
  model_signature: string;
  capability_id: string;
  dataset_id: string;
  primary_metric: string;
  primary_value: number | null;
  normalized_quality_score: number | null;
  sample_count: number;
  observed_case_count: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_mean_ms: number | null;
  provider_cost_status: 'complete' | 'partial' | 'unavailable' | 'local_not_applicable';
  provider_cost_known: boolean;
  provider_cost_priced_cases: number;
  provider_cost_total_cases: number;
  provider_cost_coverage_rate: number | null;
  provider_cost_total_usd: number | null;
  provider_cost_per_case_usd: number | null;
  provider_cost_per_1k_cases_usd: number | null;
  input_tokens_total: number | null;
  output_tokens_total: number | null;
  failure_count: number;
  failure_rate: number | null;
  observed_quality_latency_pareto: boolean;
  known_provider_cost_quality_pareto: boolean;
}

export interface DecisionPayload {
  schema_version: string;
  quality_policy: QualityPolicy;
  cohort_policy: {
    policy_id: string;
    description: string;
    benchmark_signatures: Record<string, string>;
  };
  model_summaries: DecisionModelSummary[];
  capability_summaries: DecisionCapabilitySummary[];
  dataset_summaries: DecisionDatasetSummary[];
}

export interface OverviewPayload {
  schema_version: string;
  fixture?: boolean;
  models: DashboardModel[];
  capabilities: string[];
  cells: CapabilityCell[];
  runs: Array<Record<string, unknown>>;
  decision?: DecisionPayload;
}

export interface FamilyBreakdown {
  model_key: string;
  family: string;
  value: number;
  sample_count: number;
}

export type DisagreementOutcome =
  | 'both_correct'
  | 'a_only_correct'
  | 'b_only_correct'
  | 'both_wrong'
  | 'pipeline_failure';

export interface Disagreement {
  sample_id: string;
  model_a: string;
  model_b: string;
  outcome: DisagreementOutcome;
  family: string | null;
  difficulty: string | null;
  challenge_type: string | null;
  dataset_id: string;
  case_a: string;
  case_b: string;
  value_a: number | null;
  value_b: number | null;
  expected?: unknown;
  prediction_a?: unknown;
  prediction_b?: unknown;
}

export interface PairwiseComparison {
  model_a: string;
  model_b: string;
  paired_count: number;
  delta_b_minus_a: number | null;
  ci95_low: number | null;
  ci95_high: number | null;
  both_correct: number;
  model_a_only: number;
  model_b_only: number;
  both_wrong: number;
  mcnemar_exact_p: number | null;
  practical_delta: number | null;
  exceeds_practical_delta: boolean | null;
}

export interface CapabilityPayload {
  schema_version: string;
  fixture?: boolean;
  capability_id: string;
  cells: CapabilityCell[];
  benchmark_signatures: string[];
  family_breakdown: FamilyBreakdown[];
  disagreements: Disagreement[];
  comparison?: PairwiseComparison;
  decision?: {
    capability_summaries: DecisionCapabilitySummary[];
    dataset_summaries: DecisionDatasetSummary[];
  };
}

export interface ModelPayload {
  schema_version: string;
  model_signature: string;
  model: (DashboardModel & {
    run_id?: string;
    completed_at_utc?: string;
    run_status?: string;
    git_commit?: string | null;
    quantization?: string | null;
    artifact_format?: string | null;
  }) | null;
  current_cells: CapabilityCell[];
  history: Array<CapabilityCell & { result_state: string }>;
  decision_summary?: DecisionModelSummary | null;
}

export interface RunPayload {
  schema_version: string;
  run: {
    run_id: string;
    run_group?: string;
    created_at_utc?: string;
    completed_at_utc?: string;
    status: string;
    suite_id?: string;
    suite_version?: string;
    profile?: string;
    git_commit?: string | null;
  };
  models: Array<DashboardModel & {
    run_id?: string;
    execution_signature?: string;
    quantization?: string | null;
  }>;
  cells: Array<CapabilityCell & { status: string }>;
  resources: Array<ResourceSummary & {
    model_key: string;
    capability_id: string;
    execution_signature?: string | null;
  }>;
  timeline: Array<{
    event_type: string;
    timestamp_utc: string;
    model_key?: string | null;
    capability_id?: string | null;
    status?: string | null;
    duration_ms?: number | null;
    error_type?: string | null;
    error_message?: string | null;
  }>;
  failure_summary: Array<{
    event_type: string;
    error_type: string;
    count: number;
    first_at: string;
    last_at: string;
  }>;
}
