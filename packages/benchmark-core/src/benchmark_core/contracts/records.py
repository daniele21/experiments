from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from benchmark_core.contracts.evaluation import MetricResult, TaskResult
from benchmark_core.contracts.inference import InferenceResult
from benchmark_core.contracts.media import OutputArtifact


@dataclass(frozen=True)
class RawInferenceRecord:
    run_id: str
    run_group: str
    suite_id: str
    task_id: str
    sample_id: str
    provider_id: str
    model_id: str
    raw_output: Any
    normalized_output: Any
    latency_ms: float
    output_artifacts: tuple[OutputArtifact, ...] = ()
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    valid: bool = True
    error_kind: str | None = None
    error_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inference_result(
        cls,
        *,
        run_id: str,
        run_group: str,
        suite_id: str,
        task_id: str,
        sample_id: str,
        result: InferenceResult,
        metadata: Mapping[str, Any] | None = None,
    ) -> RawInferenceRecord:
        error = result.error
        return cls(
            run_id=run_id,
            run_group=run_group,
            suite_id=suite_id,
            task_id=task_id,
            sample_id=sample_id,
            provider_id=result.provider_id,
            model_id=result.model_id,
            raw_output=result.raw_output,
            normalized_output=result.normalized_output,
            latency_ms=result.latency_ms,
            output_artifacts=result.output_artifacts,
            input_tokens=result.usage.input_tokens,
            cached_input_tokens=result.usage.cached_input_tokens,
            output_tokens=result.usage.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            valid=result.valid,
            error_kind=error.kind if error is not None else None,
            error_message=error.message if error is not None else None,
            metadata=dict(metadata or result.metadata),
        )


@dataclass(frozen=True)
class EvaluationRecord:
    run_id: str
    task_id: str
    sample_id: str
    evaluator_version: str
    expected: Any
    prediction: Any
    metrics: tuple[MetricResult, ...] = ()
    valid: bool = True
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_task_result(
        cls,
        *,
        run_id: str,
        evaluator_version: str,
        result: TaskResult,
    ) -> EvaluationRecord:
        return cls(
            run_id=run_id,
            task_id=result.task_id,
            sample_id=result.sample_id,
            evaluator_version=evaluator_version,
            expected=result.expected,
            prediction=result.prediction,
            metrics=result.metrics,
            valid=result.valid,
            error=result.error,
            metadata=result.metadata,
        )


@dataclass(frozen=True)
class AggregateMetricRecord:
    model_key: str
    task_id: str
    metric: str
    value: int | float | None
    sample_count: int
    failure_count: int = 0
    dataset_id: str | None = None
    profile: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_key.strip():
            raise ValueError("model_key must not be empty")
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.metric.strip():
            raise ValueError("metric must not be empty")
        if self.sample_count < 0:
            raise ValueError("sample_count must be >= 0")
        if self.failure_count < 0:
            raise ValueError("failure_count must be >= 0")
