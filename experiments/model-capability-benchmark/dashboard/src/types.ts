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
