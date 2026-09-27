from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from benchmark_core.contracts import (
    GenerationConfig,
    InferenceRequest,
    InferenceResult,
    ModelCapabilities,
    Sample,
    TaskResult,
)


@dataclass(frozen=True)
class TaskMetricSpec:
    name: str
    primary: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("metric name must not be empty")


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    version: str
    plugin_id: str
    evaluator_id: str
    evaluator_version: str = "1"
    required_capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    compatible_datasets: tuple[str, ...] = ()
    prompt_id: str | None = None
    prompt_version: str | None = None
    metrics: tuple[TaskMetricSpec, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("task_id", self.task_id),
            ("version", self.version),
            ("plugin_id", self.plugin_id),
            ("evaluator_id", self.evaluator_id),
            ("evaluator_version", self.evaluator_version),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")

        if (self.prompt_id is None) != (self.prompt_version is None):
            raise ValueError("prompt_id and prompt_version must be provided together")
        if self.prompt_id is not None and not self.prompt_id.strip():
            raise ValueError("prompt_id must not be empty")
        if self.prompt_version is not None and not self.prompt_version.strip():
            raise ValueError("prompt_version must not be empty")

        dataset_ids = [dataset_id.strip() for dataset_id in self.compatible_datasets]
        if any(not dataset_id for dataset_id in dataset_ids):
            raise ValueError("compatible_datasets must not contain empty values")
        if len(dataset_ids) != len(set(dataset_ids)):
            raise ValueError("compatible_datasets must not contain duplicates")

        metric_names = [metric.name for metric in self.metrics]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("task metrics must have unique names")


@dataclass(frozen=True)
class TaskExecutionContext:
    run_id: str
    dataset_id: str
    profile: str
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("dataset_id", self.dataset_id),
            ("profile", self.profile),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")


@runtime_checkable
class BenchmarkTask(Protocol):
    @property
    def spec(self) -> TaskSpec:
        """Static, versioned task definition."""

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        """Translate one normalized sample into a provider-agnostic inference request."""

    def evaluate(
        self,
        sample: Sample,
        inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        """Evaluate observable inference output against the sample expectation."""
