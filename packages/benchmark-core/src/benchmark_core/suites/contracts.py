from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from benchmark_core.contracts import GenerationConfig

MetricSource = Literal["task_metric", "evaluation", "inference"]
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


@dataclass(frozen=True)
class CapabilityMetricSpec:
    name: str
    source: MetricSource
    reducer: str
    field: str | None = None
    primary: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)

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


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    task_id: str
    dataset_ids: tuple[str, ...]
    metrics: tuple[CapabilityMetricSpec, ...]
    description: str | None = None
    tags: tuple[str, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

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

        names = [metric.name for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("capability metrics must have unique names")
        if sum(metric.primary for metric in self.metrics) != 1:
            raise ValueError("capability must declare exactly one primary metric")


@dataclass(frozen=True)
class BenchmarkSuiteSpec:
    suite_id: str
    version: str
    default_profile: str
    generation: GenerationConfig
    capabilities: tuple[CapabilitySpec, ...]
    description: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

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
