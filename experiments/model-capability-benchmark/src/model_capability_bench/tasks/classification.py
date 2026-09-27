from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from benchmark_core import (
    InferenceRequest,
    InferenceResult,
    MetricResult,
    Sample,
    TaskExecutionContext,
    TaskResult,
    TaskSpec,
)


class IntentClassificationTask:
    def __init__(self, spec: TaskSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> TaskSpec:
        return self._spec

    def _option(self, name: str) -> str:
        value = self.spec.options.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Task {self.spec.task_id!r} requires non-empty option {name!r}"
            )
        return value

    def _labels(self, sample: Sample) -> tuple[str, ...]:
        metadata_key = self._option("labels_metadata_key")
        raw = sample.metadata.get(metadata_key)
        if (
            not isinstance(raw, Sequence)
            or isinstance(raw, (str, bytes))
            or not raw
            or not all(isinstance(label, str) and label.strip() for label in raw)
        ):
            raise ValueError(
                f"Sample {sample.sample_id!r} metadata {metadata_key!r} "
                "must contain non-empty label strings"
            )
        labels = tuple(str(label) for label in raw)
        if len(labels) != len(set(labels)):
            raise ValueError(f"Sample {sample.sample_id!r} labels must be unique")
        return labels

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        output_field = self._option("output_field")
        labels = self._labels(sample)
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            system_prompt=self._option("instruction"),
            response_schema={
                "type": "object",
                "properties": {
                    output_field: {
                        "type": "string",
                        "enum": list(labels),
                    }
                },
                "required": [output_field],
                "additionalProperties": False,
            },
            generation=context.generation,
            task_metadata={
                "task_id": self.spec.task_id,
                "task_version": self.spec.version,
                "prompt_id": self.spec.prompt_id,
                "prompt_version": self.spec.prompt_version,
                "dataset_id": context.dataset_id,
            },
        )

    def evaluate(
        self,
        sample: Sample,
        inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        output_field = self._option("output_field")
        prediction: Any = None
        if isinstance(inference.normalized_output, Mapping):
            prediction = inference.normalized_output.get(output_field)

        expected = sample.expected
        valid = inference.valid and prediction is not None
        correct = bool(valid and prediction == expected)
        error = inference.error.message if inference.error is not None else None
        if inference.valid and prediction is None:
            error = f"normalized output is missing field {output_field!r}"

        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=expected,
            metrics=(
                MetricResult(
                    name="accuracy",
                    value=float(correct),
                    primary=True,
                ),
            ),
            valid=valid,
            error=error,
            metadata={"dataset_id": context.dataset_id},
        )
