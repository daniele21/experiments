from __future__ import annotations

from collections.abc import Sequence

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.runner import run_experiment


class _DeterministicFakeProvider:
    name = "fake"

    def evaluate(self, state, questions: Sequence[QuestionSpec]) -> ProviderResult:
        answers = {}
        for question in questions:
            if question.type == "choice":
                value = next(iter(question.criteria or {"fallback": "fallback"}))
            elif question.type == "noul":
                value = 0.0
            else:
                value = 0.0
            answers[question.id] = Decision(
                question_id=question.id,
                value=value,
                confidence=0.5,
                predicted_probability=0.5,
            )
        return ProviderResult(
            provider=self.name,
            model="fake-model",
            answers=answers,
            latency_ms=10.0,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
        )


def test_run_single_scaling_experiment_has_all_question_counts_and_input_state():
    frame = run_experiment("scaling", _DeterministicFakeProvider(), scaling_repeats=1)

    assert frame["experiment"].unique().tolist() == ["03-parallel-scaling"]
    assert frame["question_count"].tolist() == [1, 2, 4, 8, 16, 32]
    assert frame["input_state"].str.contains("Stripe integration").all()


def test_run_single_workflow_persists_case_input_and_decision_trace():
    frame = run_experiment("workflow", _DeterministicFakeProvider())

    finals = frame[frame["question_id"].eq("final_action")]
    assert len(finals) == 6
    assert finals["input_state"].notna().all()
    assert finals["decision_trace"].notna().all()
    assert finals["decision_trace"].str.contains("intermediate").all()
