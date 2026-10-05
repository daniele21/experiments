export interface DashboardModel {
  model_key: string;
  model_id: string;
  effective_model_id: string;
  model_signature: string;
  runtime_key: string;
  provider_key: string;
  deployment: string;
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
}

export interface OverviewPayload {
  schema_version: string;
  fixture?: boolean;
  models: DashboardModel[];
  capabilities: string[];
  cells: CapabilityCell[];
  runs: Array<Record<string, unknown>>;
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
