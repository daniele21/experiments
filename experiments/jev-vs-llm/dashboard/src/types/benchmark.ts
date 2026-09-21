/**
 * benchmark.ts
 * TypeScript interfaces for benchmark data structures, metrics, and models.
 */

export interface BenchmarkMetadata {
  run_group: string;
  suite: string;
  runner_location: string;
  pricing_as_of: string;
  total_rows: number;
  is_local_zero_cost: boolean;
}

export interface ModelBadge {
  label: string;
  class: string;
}

export interface LeaderboardEntry {
  rank: number;
  medal: string;
  series: string;
  model: string;
  provider: string;
  accuracy: number;
  accuracy_pct: string;
  delta_str: string;
  delta_class: 'leader' | 'close' | 'moderate' | 'far';
  latency_p50_ms: number;
  latency_str: string;
  speed_str: string;
  speed_class: string;
  vs_leader_speed: string;
  valid_rate_pct: string;
  valid_count: number;
  total_count: number;
  badges: ModelBadge[];
  quant_label?: string;
}

export interface KpiCardsData {
  leader?: LeaderboardEntry;
  fastest?: LeaderboardEntry;
  sweet_spot?: LeaderboardEntry;
  total_models: number;
  total_requests: number;
}

export interface ExperimentStatus {
  id: string;
  title: string;
  full_title: string;
  description: string;
  cli_command: string;
  has_data: boolean;
  count: number;
  models_count: number;
  badge_text: string;
  badge_class: string;
}

export interface ModelSpec {
  series: string;
  model: string;
  provider: string;
  accuracy: number;
  latency_p50_ms: number;
}

export interface OverviewRow {
  provider: string;
  model: string;
  series: string;
  accuracy: number;
  valid_rate: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  cost_per_request_usd: number;
  cost_per_1k_requests_usd: number;
  run_cost_usd: number;
  requests: number;
  valid_requests: number;
}

export interface CaseDecision {
  question_id: string;
  expected: string;
  actual: string;
  correct: boolean;
  valid: boolean;
  confidence: number;
  error: string | null;
}

export interface BenchmarkCaseItem {
  series: string;
  model: string;
  case_id: string;
  status: 'Correct' | 'Wrong' | 'Invalid' | 'Valid';
  status_class: 'good' | 'bad' | 'neutral';
  latency_ms: number;
  input_state: string;
  expected: string;
  actual: string;
  correct: boolean;
  valid: boolean;
  error: string | null;
  difficulty: string;
  decisions: CaseDecision[];
}

export interface PerClassAccuracy {
  series: string;
  class: string;
  cases: number;
  valid_rate: number;
  accuracy: number;
  top_wrong: string;
}

export interface ConfusionPair {
  pair: string;
  count: number;
  series: string;
}

export interface RoutingData {
  summary: Array<Record<string, any>>;
  confusions: ConfusionPair[];
  per_class: PerClassAccuracy[];
  cases: BenchmarkCaseItem[];
  errors: Array<Record<string, any>>;
}

export interface CalibrationData {
  summary: Array<Record<string, any>>;
  rel_bins: Array<{ series: string; predicted_probability: number; accuracy: number; count: number }>;
  coverage: Array<{ series: string; coverage: number; accuracy: number; threshold: number }>;
  difficulty: Array<{ series: string; difficulty: string; accuracy: number; n: number }>;
  cases: BenchmarkCaseItem[];
  errors: Array<Record<string, any>>;
}

export interface ScalingData {
  summary: Array<{ series: string; question_count: number; latency_p50_ms: number; latency_p95_ms: number; cost_per_request_usd: number }>;
  details: Array<Record<string, any>>;
  errors: Array<Record<string, any>>;
}

export interface GenericExperimentData {
  summary: Array<Record<string, any>>;
  cases: BenchmarkCaseItem[];
  errors: Array<Record<string, any>>;
}

export interface PricingInfo {
  as_of: string;
  currency: string;
  processing: string;
  prices_per_million_tokens: Record<string, { input: number; cached_input: number | null; output: number; source: string }>;
}

export interface BenchmarkPayload {
  metadata: BenchmarkMetadata;
  experiments: Record<string, ExperimentStatus>;
  models: ModelSpec[];
  leaderboard: LeaderboardEntry[];
  kpi_cards: KpiCardsData;
  overview: OverviewRow[];
  routing: RoutingData;
  calibration: CalibrationData;
  scaling: ScalingData;
  workflow: GenericExperimentData;
  agent: GenericExperimentData;
  pricing: PricingInfo;
}
