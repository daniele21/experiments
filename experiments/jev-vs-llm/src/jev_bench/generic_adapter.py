from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from benchmark_core import (
    InferenceError,
    InferenceRequest,
    InferenceResult,
    TokenUsage,
)

from jev_bench.models import QuestionSpec
from jev_bench.providers.base import DecisionProvider

LEGACY_QUESTIONS_METADATA_KEY = "jev.questions"


class DecisionProviderInferenceAdapter:
    """Expose an existing Jev DecisionProvider through the generic inference contract."""

    def __init__(self, provider: DecisionProvider) -> None:
        self.provider = provider
        self.provider_id = f"jev-decision:{provider.name}"

    def _configuration_error(
        self,
        request: InferenceRequest,
        message: str,
    ) -> InferenceResult:
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=str(getattr(self.provider, "model", "unknown")),
            raw_output=None,
            latency_ms=0.0,
            valid=False,
            error=InferenceError(
                kind="configuration",
                message=message,
                retryable=False,
            ),
            metadata={"request_id": request.request_id, "adapter": "jev-decision-provider"},
        )

    def generate(self, request: InferenceRequest) -> InferenceResult:
        if request.input is None:
            return self._configuration_error(
                request,
                "Jev decision adapter requires InferenceRequest.input as state",
            )

        raw_questions: Any = request.task_metadata.get(LEGACY_QUESTIONS_METADATA_KEY)
        if (
            not isinstance(raw_questions, Sequence)
            or isinstance(raw_questions, (str, bytes))
            or not raw_questions
            or not all(isinstance(question, QuestionSpec) for question in raw_questions)
        ):
            return self._configuration_error(
                request,
                f"task_metadata[{LEGACY_QUESTIONS_METADATA_KEY!r}] must contain QuestionSpec items",
            )

        questions = list(raw_questions)
        result = self.provider.evaluate(request.input, questions)
        error = None
        if not result.valid:
            error = InferenceError(
                kind="provider",
                message=result.error or "legacy decision provider returned an invalid result",
                retryable=False,
            )

        metadata = {
            "request_id": request.request_id,
            "adapter": "jev-decision-provider",
            "question_ids": [question.id for question in questions],
        }
        if result.error and result.valid:
            metadata["legacy_warning"] = result.error

        return InferenceResult(
            provider_id=result.provider,
            model_id=result.model,
            raw_output=result.raw,
            normalized_output=result,
            latency_ms=result.latency_ms,
            usage=TokenUsage(
                input_tokens=result.input_tokens,
                cached_input_tokens=result.cached_input_tokens,
                output_tokens=result.output_tokens,
            ),
            estimated_cost_usd=result.estimated_cost_usd,
            valid=result.valid,
            error=error,
            metadata=metadata,
        )
