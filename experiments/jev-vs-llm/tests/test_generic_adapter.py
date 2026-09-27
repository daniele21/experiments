from __future__ import annotations

from collections.abc import Sequence

from benchmark_core import InferenceProvider, InferenceRequest

from jev_bench.generic_adapter import (
    LEGACY_QUESTIONS_METADATA_KEY,
    DecisionProviderInferenceAdapter,
)
from jev_bench.models import Decision, ProviderResult, QuestionSpec


class _FakeDecisionProvider:
    name = "fake-decision"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(
        self,
        state: object,
        questions: Sequence[QuestionSpec],
    ) -> ProviderResult:
        self.calls += 1
        question = questions[0]
        return ProviderResult(
            provider=self.name,
            model=self.model,
            answers={
                question.id: Decision(
                    question_id=question.id,
                    value="billing",
                    confidence=0.9,
                    predicted_probability=0.95,
                )
            },
            latency_ms=7.5,
            input_tokens=12,
            cached_input_tokens=3,
            output_tokens=4,
            estimated_cost_usd=0.002,
            raw={"fixture": True, "state": state},
        )


def test_legacy_decision_provider_satisfies_generic_provider_through_adapter() -> None:
    legacy = _FakeDecisionProvider()
    adapter = DecisionProviderInferenceAdapter(legacy)
    question = QuestionSpec(
        id="department",
        type="choice",
        instructions="Route the request.",
        criteria={"billing": "Billing", "technical": "Technical"},
    )
    request = InferenceRequest(
        request_id="case-1",
        input="I was charged twice.",
        task_metadata={LEGACY_QUESTIONS_METADATA_KEY: [question]},
    )

    result = adapter.generate(request)

    assert isinstance(adapter, InferenceProvider)
    assert legacy.calls == 1
    assert result.valid is True
    assert result.provider_id == "fake-decision"
    assert result.model_id == "fake-model"
    assert result.usage.input_tokens == 12
    assert result.usage.cached_input_tokens == 3
    assert result.usage.output_tokens == 4
    assert result.estimated_cost_usd == 0.002
    assert result.normalized_output.answers["department"].value == "billing"
    assert result.metadata["question_ids"] == ["department"]


def test_adapter_returns_typed_configuration_error_without_questions() -> None:
    legacy = _FakeDecisionProvider()
    adapter = DecisionProviderInferenceAdapter(legacy)
    request = InferenceRequest(request_id="case-invalid", input="hello")

    result = adapter.generate(request)

    assert legacy.calls == 0
    assert result.valid is False
    assert result.error is not None
    assert result.error.kind == "configuration"
