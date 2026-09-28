from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
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


class MathematicalReasoningTask:
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

    @staticmethod
    def _normalized(value: Any) -> str:
        text = str(value).strip()
        try:
            number = Decimal(text)
        except InvalidOperation:
            return " ".join(text.lower().split())
        normalized = number.normalize()
        return format(normalized, "f")

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        output_field = self._option("output_field")
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            system_prompt=self._option("instruction"),
            response_schema={
                "type": "object",
                "properties": {
                    output_field: {"type": "string"},
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

        parse_valid = isinstance(prediction, str) and bool(prediction.strip())
        valid = bool(inference.valid and parse_valid)
        correct = bool(
            valid
            and self._normalized(prediction)
            == self._normalized(sample.expected)
        )

        error = inference.error.message if inference.error is not None else None
        if inference.valid and not valid:
            error = f"normalized output must contain string field {output_field!r}"

        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=sample.expected,
            metrics=(
                MetricResult(
                    name="final_answer_accuracy",
                    value=float(correct),
                    primary=True,
                ),
                MetricResult(name="parse_valid", value=float(valid)),
            ),
            valid=valid,
            error=error,
            metadata={"dataset_id": context.dataset_id},
        )
