from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Literal

from benchmark_core.contracts import GenerationConfig

MetricSource = Literal["task_metric", "evaluation", "inference"]
ContextSource = Literal["literal", "dataset_metadata"]
BenchmarkSelectionStrategy = Literal["profile", "fixed", "stratified"]
MetricReducer = Literal[
    "mean",
    "sum",
    "rate",
    "macro_f1",
    "in_scope_accuracy",
    "oos_detection",
    "ece",
    "brier",
    "p50",
    "p95",
    "invalid_rate",
]


@dataclasses.dataclass(frozen=True)
class CapabilityMetricSpec:
    name: str
    source: MetricSource
    reducer: str
    field: str | None = None
    primary: bool = False
    options: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("metric name must not be empty")
        if self.source not in {"task_metric", "evaluation", "inference"}:
            raise ValueError(f"Unsupported metric source: {self.source}")
        if self.reducer not in {
            "mean",
            "sum",
            "rate",
            "macro_f1",
            "in_scope_accuracy",
            "oos_detection",
            "ece",
            "brier",
            "p50",
            "p95",
            "invalid_rate",
        }:
            raise ValueError(f"Unsupported metric reducer: {self.reducer}")
        if self.field is not None and not self.field.strip():
            raise ValueError("metric field must not be empty")


@dataclasses.dataclass(frozen=True)
class CapabilityContextBinding:
    key: str
    source: ContextSource
    dataset_id: str | None = None
    field: str | None = None
    value: Any = None
    append: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("context binding key must not be empty")
        if self.source not in {"literal", "dataset_metadata"}:
            raise ValueError(f"Unsupported context source: {self.source}")

        if self.source == "dataset_metadata":
            if self.dataset_id is None or not self.dataset_id.strip():
                raise ValueError(
                    "dataset_metadata context binding requires dataset_id"
                )
            if self.field is None or not self.field.strip():
                raise ValueError("dataset_metadata context binding requires field")
            if self.value is not None:
                raise ValueError(
                    "dataset_metadata context binding cannot define literal value"
                )
        elif self.dataset_id is not None or self.field is not None:
            raise ValueError(
                "literal context binding cannot reference dataset_id or field"
            )


@dataclasses.dataclass(frozen=True)
class BenchmarkSelectionQuota:
    match: Mapping[str, Any]
    count: int

    def __post_init__(self) -> None:
        if not self.match:
            raise ValueError("selection quota match must not be empty")
        if self.count <= 0:
            raise ValueError("selection quota count must be > 0")


@dataclasses.dataclass(frozen=True)
class BenchmarkSelectionSpec:
    strategy: BenchmarkSelectionStrategy = "profile"
    quotas: tuple[BenchmarkSelectionQuota, ...] = ()

    def __post_init__(self) -> None:
        if self.strategy not in {"profile", "fixed", "stratified"}:
            raise ValueError(f"Unsupported selection strategy: {self.strategy}")
        if self.strategy == "stratified" and not self.quotas:
            raise ValueError("stratified selection requires at least one quota")
        if self.strategy != "stratified" and self.quotas:
            raise ValueError("selection quotas are only valid for stratified selection")


@dataclasses.dataclass(frozen=True)
class BenchmarkTierSpec:
    tier_id: str
    max_cases: int | None = None
    dataset_max_cases: Mapping[str, int | None] = dataclasses.field(
        default_factory=dict
    )
    selection: BenchmarkSelectionSpec = dataclasses.field(
        default_factory=BenchmarkSelectionSpec
    )
    target_local_seconds: float | None = None
    hard_local_seconds: float | None = None
    target_api_cost_usd: float | None = None
    hard_api_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if not self.tier_id.strip():
            raise ValueError("benchmark tier_id must not be empty")
        if self.max_cases is not None and self.max_cases <= 0:
            raise ValueError("benchmark max_cases must be > 0 or null")
        for dataset_id, value in self.dataset_max_cases.items():
            if not str(dataset_id).strip():
                raise ValueError("benchmark dataset keys must not be empty")
            if value is not None and value <= 0:
                raise ValueError(
                    f"benchmark dataset limit for {dataset_id!r} must be > 0 or null"
                )
        for field_name, value in (
            ("target_local_seconds", self.target_local_seconds),
            ("hard_local_seconds", self.hard_local_seconds),
            ("target_api_cost_usd", self.target_api_cost_usd),
            ("hard_api_cost_usd", self.hard_api_cost_usd),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be > 0 or null")
        if (
            self.target_local_seconds is not None
            and self.hard_local_seconds is not None
            and self.target_local_seconds > self.hard_local_seconds
        ):
            raise ValueError("target_local_seconds cannot exceed hard_local_seconds")
        if (
            self.target_api_cost_usd is not None
            and self.hard_api_cost_usd is not None
            and self.target_api_cost_usd > self.hard_api_cost_usd
        ):
            raise ValueError("target_api_cost_usd cannot exceed hard_api_cost_usd")

    def max_cases_for(
        self,
        dataset_id: str,
        *,
        fallback: int | None,
    ) -> int | None:
        if dataset_id in self.dataset_max_cases:
            return self.dataset_max_cases[dataset_id]
        return self.max_cases if self.max_cases is not None else fallback


@dataclasses.dataclass(frozen=True)
class CapabilityComparisonSpec:
    practical_delta: float | None = None
    metric: str | None = None

    def __post_init__(self) -> None:
        if self.practical_delta is not None and not 0 <= self.practical_delta <= 1:
            raise ValueError("practical_delta must be between 0 and 1")
        if self.metric is not None and not self.metric.strip():
            raise ValueError("comparison metric must not be empty")


@dataclasses.dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    task_id: str
    dataset_ids: tuple[str, ...]
    metrics: tuple[CapabilityMetricSpec, ...]
    description: str | None = None
    tags: tuple[str, ...] = ()
    context_bindings: tuple[CapabilityContextBinding, ...] = ()
    benchmark_tiers: Mapping[str, BenchmarkTierSpec] = dataclasses.field(
        default_factory=dict
    )
    comparison: CapabilityComparisonSpec = dataclasses.field(
        default_factory=CapabilityComparisonSpec
    )
    options: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be empty")
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.dataset_ids:
            raise ValueError("capability must reference at least one dataset")
        if any(not dataset_id.strip() for dataset_id in self.dataset_ids):
            raise ValueError("dataset_ids must not contain empty values")
        if len(self.dataset_ids) != len(set(self.dataset_ids)):
            raise ValueError("dataset_ids must not contain duplicates")
        if not self.metrics:
            raise ValueError("capability must declare at least one metric")

        context_keys = [binding.key for binding in self.context_bindings]
        if len(context_keys) != len(set(context_keys)):
            raise ValueError("capability context binding keys must be unique")

        names = [metric.name for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("capability metrics must have unique names")
        if sum(metric.primary for metric in self.metrics) != 1:
            raise ValueError("capability must declare exactly one primary metric")

        for tier_id, tier in self.benchmark_tiers.items():
            if tier_id != tier.tier_id:
                raise ValueError("benchmark tier mapping key must match tier_id")
            unknown_datasets = set(tier.dataset_max_cases) - set(self.dataset_ids)
            if unknown_datasets:
                raise ValueError(
                    "benchmark tier references datasets outside capability: "
                    + ", ".join(sorted(unknown_datasets))
                )

    def benchmark_tier(self, profile_id: str) -> BenchmarkTierSpec | None:
        return self.benchmark_tiers.get(profile_id)


@dataclasses.dataclass(frozen=True)
class BenchmarkSuiteSpec:
    suite_id: str
    version: str
    default_profile: str
    generation: GenerationConfig
    capabilities: tuple[CapabilitySpec, ...]
    description: str | None = None
    options: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("suite_id", self.suite_id),
            ("version", self.version),
            ("default_profile", self.default_profile),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if not self.capabilities:
            raise ValueError("suite must declare at least one capability")
        ids = [capability.capability_id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("suite capability IDs must be unique")
