from __future__ import annotations

from collections.abc import Sequence

from benchmark_core import (
    TaskExecutionContext,
    TaskSpec,
)

from jev_bench.decision_task import (
    JevDecisionTaskAdapter,
    benchmark_case_to_sample,
    decision_correct,
)
from jev_bench.generic_adapter import DecisionProviderInferenceAdapter
from jev_bench.models import BenchmarkCase, Decision, ProviderResult, QuestionSpec
from jev_bench.runner import _rows_for_case


class _FixtureDecisionProvider:
    name = "fixture-decision"

    def evaluate(
        self,
        state: object,
        questions: Sequence[QuestionSpec],
    ) -> ProviderResult:
        answers = {
            question.id: Decision(
                question_id=question.id,
                value="billing" if question.type == "choice" else 0.8,
                confidence=0.75,
                predicted_probability=0.8,
            )
            for question in questions
        }
        return ProviderResult(
            provider=self.name,
            model="fixture-model",
            answers=answers,
            latency_ms=4.0,
            input_tokens=5,
            output_tokens=2,
            estimated_cost_usd=0.001,
        )


def _task(questions: list[QuestionSpec]) -> JevDecisionTaskAdapter:
    return JevDecisionTaskAdapter(
        TaskSpec(
            task_id="jev-routing",
            version="1",
            plugin_id="jev-decision",
            evaluator_id="jev-bounded-decision",
            evaluator_version="1",
            compatible_datasets=("fixture",),
        ),
        questions,
    )


def test_generic_decision_task_matches_legacy_row_semantics() -> None:
    question = QuestionSpec(
        id="department",
        type="choice",
        instructions="Route the request.",
        criteria={"billing": "Billing", "technical": "Technical"},
    )
    case = BenchmarkCase(
        case_id="case-1",
        state="I was charged twice.",
        expected={"department": "billing"},
        metadata={"difficulty": "fixture"},
    )
    provider = _FixtureDecisionProvider()
    legacy_result = provider.evaluate(case.state, [question])
    legacy_row = _rows_for_case(
        "01-routing",
        case,
        [question],
        legacy_result,
    )[0]

    task = _task([question])
    sample = benchmark_case_to_sample(case)
    context = TaskExecutionContext(
        run_id="run-1",
        dataset_id="fixture",
        profile="smoke",
    )
    request = task.build_request(sample, context)
    inference = DecisionProviderInferenceAdapter(provider).generate(request)
    result = task.evaluate(sample, inference, context)

    detail = result.metadata["question_results"][0]
    assert result.valid is True
    assert result.prediction == {"department": "billing"}
    assert detail["expected"] == legacy_row["expected"]
    assert detail["actual"] == legacy_row["actual"]
    assert detail["correct"] == legacy_row["correct"]
    assert detail["confidence"] == legacy_row["confidence"]
    assert detail["predicted_probability"] == legacy_row["predicted_probability"]


def test_generic_decision_task_preserves_missing_answer_semantics() -> None:
    question = QuestionSpec(
        id="department",
        type="choice",
        instructions="Route the request.",
        criteria={"billing": "Billing"},
    )
    case = BenchmarkCase(
        case_id="case-missing",
        state="billing",
        expected={"department": "billing"},
    )
    provider_result = ProviderResult(
        provider="fixture",
        model="fixture-model",
        answers={},
        latency_ms=1.0,
        valid=True,
    )

    class _MissingProvider:
        name = "missing"

        def evaluate(self, state, questions):
            return provider_result

    task = _task([question])
    sample = benchmark_case_to_sample(case)
    context = TaskExecutionContext(
        run_id="run-1",
        dataset_id="fixture",
        profile="smoke",
    )
    inference = DecisionProviderInferenceAdapter(_MissingProvider()).generate(
        task.build_request(sample, context)
    )
    result = task.evaluate(sample, inference, context)

    assert result.valid is False
    assert result.error == "missing answer"
    assert result.prediction == {"department": None}
    assert result.metrics[0].value == 0.0


def test_decision_correct_preserves_noul_and_score_thresholds() -> None:
    noul = QuestionSpec(
        id="probability",
        type="noul",
        instructions="Probability",
    )
    score = QuestionSpec(
        id="score",
        type="score",
        instructions="Score",
    )

    assert decision_correct(0.6, 0.9, noul) is True
    assert decision_correct(0.4, 0.9, noul) is False
    assert decision_correct(3.0, 3.5, score) is True
    assert decision_correct(3.0, 3.6, score) is False
