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

from jev_bench.generic_adapter import LEGACY_QUESTIONS_METADATA_KEY
from jev_bench.models import BenchmarkCase, ProviderResult, QuestionSpec


def decision_correct(
    expected: str | float,
    actual: str | float,
    question: QuestionSpec,
) -> bool:
    if question.type == "noul":
        return int(float(actual) >= 0.5) == int(float(expected) >= 0.5)
    if question.type == "score":
        return abs(float(actual) - float(expected)) <= 0.5
    return str(actual) == str(expected)


def benchmark_case_to_sample(case: BenchmarkCase) -> Sample:
    return Sample(
        sample_id=case.case_id,
        input=case.state,
        expected=dict(case.expected),
        metadata=dict(case.metadata),
    )


class JevDecisionTaskAdapter:
    """Expose bounded Jev decision semantics through the generic task contract."""

    def __init__(
        self,
        spec: TaskSpec,
        questions: Sequence[QuestionSpec],
    ) -> None:
        if not questions:
            raise ValueError("Jev decision task requires at least one question")
        self._spec = spec
        self.questions = tuple(questions)

    @property
    def spec(self) -> TaskSpec:
        return self._spec

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            generation=context.generation,
            task_metadata={
                "task_id": self.spec.task_id,
                "task_version": self.spec.version,
                "dataset_id": context.dataset_id,
                LEGACY_QUESTIONS_METADATA_KEY: self.questions,
            },
        )

    def evaluate(
        self,
        sample: Sample,
        inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        expected = sample.expected
        if not isinstance(expected, Mapping):
            raise TypeError(
                f"Sample {sample.sample_id!r} expected value must be a mapping"
            )

        result = inference.normalized_output
        if not isinstance(result, ProviderResult):
            return TaskResult(
                task_id=self.spec.task_id,
                sample_id=sample.sample_id,
                prediction=None,
                expected=expected,
                metrics=(
                    MetricResult(
                        name="question_accuracy",
                        value=0.0,
                        primary=True,
                    ),
                    MetricResult(name="complete", value=0.0),
                ),
                valid=False,
                error=(
                    inference.error.message
                    if inference.error is not None
                    else "normalized output is not a ProviderResult"
                ),
                metadata={"dataset_id": context.dataset_id, "question_results": []},
            )

        question_results: list[dict[str, Any]] = []
        prediction: dict[str, str | float | None] = {}
        correct_count = 0
        missing_count = 0

        for question in self.questions:
            expected_value = expected.get(question.id)
            decision = result.answers.get(question.id)
            actual = decision.value if decision is not None else None
            is_correct = bool(
                decision is not None
                and expected_value is not None
                and decision_correct(expected_value, decision.value, question)
            )
            if decision is None:
                missing_count += 1
            correct_count += int(is_correct)
            prediction[question.id] = actual
            question_results.append(
                {
                    "question_id": question.id,
                    "expected": expected_value,
                    "actual": actual,
                    "correct": is_correct,
                    "confidence": (
                        decision.confidence if decision is not None else None
                    ),
                    "predicted_probability": (
                        decision.predicted_probability
                        if decision is not None
                        else None
                    ),
                }
            )

        complete = bool(result.valid and missing_count == 0)
        accuracy = correct_count / len(self.questions)
        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=dict(expected),
            metrics=(
                MetricResult(
                    name="question_accuracy",
                    value=accuracy,
                    primary=True,
                ),
                MetricResult(name="complete", value=float(complete)),
            ),
            valid=complete,
            error=(
                result.error
                if result.error
                else (
                    "missing answer"
                    if result.valid and missing_count
                    else None
                )
            ),
            metadata={
                "dataset_id": context.dataset_id,
                "question_results": question_results,
                "provider": result.provider,
                "model": result.model,
            },
        )
