from __future__ import annotations

from collections.abc import Mapping
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


class QaAbstentionTask:
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
    def _expected(sample: Sample) -> tuple[str, bool]:
        if not isinstance(sample.expected, Mapping):
            raise TypeError(
                f"Sample {sample.sample_id!r} expected value must be an object"
            )
        answer = sample.expected.get("answer")
        answerable = sample.expected.get("answerable")
        if not isinstance(answer, str) or not isinstance(answerable, bool):
            raise TypeError(
                f"Sample {sample.sample_id!r} expected must contain string answer "
                "and boolean answerable"
            )
        return answer, answerable

    @staticmethod
    def _normalize_answer(value: str) -> str:
        return " ".join(value.strip().lower().split())

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            system_prompt=self._option("instruction"),
            response_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "abstain": {"type": "boolean"},
                },
                "required": ["answer", "abstain"],
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
        expected_answer, answerable = self._expected(sample)
        prediction: Any = inference.normalized_output

        predicted_answer: str | None = None
        abstain: bool | None = None
        if isinstance(prediction, Mapping):
            raw_answer = prediction.get("answer")
            raw_abstain = prediction.get("abstain")
            if isinstance(raw_answer, str):
                predicted_answer = raw_answer
            if isinstance(raw_abstain, bool):
                abstain = raw_abstain

        valid = bool(
            inference.valid
            and predicted_answer is not None
            and abstain is not None
        )
        expected_abstain = not answerable
        abstention_correct = bool(valid and abstain == expected_abstain)
        exact_match: float | None
        if answerable and valid and not abstain and predicted_answer is not None:
            exact_match = float(
                self._normalize_answer(predicted_answer)
                == self._normalize_answer(expected_answer)
            )
        elif answerable:
            exact_match = 0.0
        else:
            exact_match = None

        qa_correct = bool(
            abstention_correct
            if not answerable
            else exact_match == 1.0 and abstain is False
        )

        error = inference.error.message if inference.error is not None else None
        if inference.valid and not valid:
            error = "normalized output must contain string answer and boolean abstain"

        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=sample.expected,
            metrics=(
                MetricResult(
                    name="qa_correct",
                    value=float(qa_correct),
                    primary=True,
                ),
                MetricResult(
                    name="exact_match",
                    value=exact_match,
                ),
                MetricResult(
                    name="answerability_accuracy",
                    value=float(abstention_correct),
                ),
                MetricResult(name="parse_valid", value=float(valid)),
            ),
            valid=valid,
            error=error,
            metadata={
                "dataset_id": context.dataset_id,
                "answerable": answerable,
                "expected_abstain": expected_abstain,
            },
        )
