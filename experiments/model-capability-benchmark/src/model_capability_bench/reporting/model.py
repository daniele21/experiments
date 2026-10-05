from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportModelInfo:
    model_key: str
    model_id: str
    effective_model_id: str
    runtime_key: str
    provider_key: str
    deployment: str


@dataclass(frozen=True)
class ReportCase:
    case_id: str
    attempt: int
    sample_id: str
    dataset_id: str
    expected: Any
    prediction: Any
    inference_valid: bool
    evaluation_valid: bool
    latency_ms: float | None
    family: str | None = None
    difficulty: str | None = None
    challenge_type: str | None = None
    metrics: Mapping[str, int | float | bool | None] = field(default_factory=dict)
    error_kind: str | None = None
    error_message: str | None = None
    normalized_output: Any = None
    raw_output: Any = None


@dataclass(frozen=True)
class ReportCell:
    model_key: str
    capability_id: str
    task_id: str
    primary_metric: str
    metrics: Mapping[str, int | float | None] = field(default_factory=dict)
    sample_count: int = 0
    failure_count: int = 0
    dataset_ids: tuple[str, ...] = ()
    cases: tuple[ReportCase, ...] = ()
    truncated_case_count: int = 0

    @property
    def primary_value(self) -> int | float | None:
        return self.metrics.get(self.primary_metric)


@dataclass(frozen=True)
class ReportPairwiseComparison:
    capability_id: str
    model_a: str
    model_b: str
    metric: str
    paired_count: int
    delta_b_minus_a: float | None
    ci95_low: float | None
    ci95_high: float | None
    both_correct: int
    model_a_only: int
    model_b_only: int
    both_wrong: int
    mcnemar_exact_p: float | None
    practical_delta: float | None = None
    exceeds_practical_delta: bool | None = None


@dataclass(frozen=True)
class CapabilityReport:
    capability_id: str
    task_id: str
    dataset_ids: tuple[str, ...]
    primary_metric: str
    cells: tuple[ReportCell, ...]
    comparisons: tuple[ReportPairwiseComparison, ...] = ()


@dataclass(frozen=True)
class BenchmarkReport:
    title: str
    run_id: str
    run_group: str
    suite_id: str
    suite_version: str
    profile: str
    generated_at_utc: str
    models: tuple[ReportModelInfo, ...]
    capabilities: tuple[CapabilityReport, ...]
    events: tuple[Mapping[str, Any], ...] = ()
    cost_semantics: str = (
        "API/provider cost is shown only when reported; unknown cost is null. "
        "Local provider fee zero does not imply zero hardware/runtime cost."
    )
