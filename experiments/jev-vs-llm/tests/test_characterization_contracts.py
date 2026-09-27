from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path

import pandas as pd

from jev_bench.datasets import (
    calibration_cases,
    expense_cases,
    routing_cases,
    support_cases,
)
from jev_bench.manifest import write_manifest
from jev_bench.models import BenchmarkCase, Decision, ProviderResult, QuestionSpec
from jev_bench.runner import _rows_for_case, append_results, run_all


REQUIRED_RESULT_COLUMNS = {
    "experiment",
    "case_id",
    "input_state",
    "provider",
    "model",
    "question_id",
    "expected",
    "actual",
    "correct",
    "confidence",
    "predicted_probability",
    "latency_ms",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "valid",
    "error",
    "primary_metric",
}


class _OracleFakeProvider:
    name = "characterization-fake"

    def __init__(self) -> None:
        cases = routing_cases() + calibration_cases() + expense_cases() + support_cases()
        self._expected_by_state = {str(case.state): case.expected for case in cases}

    @staticmethod
    def _fallback_value(question: QuestionSpec) -> str | float:
        if question.type == "choice":
            if isinstance(question.criteria, dict):
                return next(iter(question.criteria))
            if isinstance(question.criteria, list):
                return question.criteria[0]
            return "fallback"
        return 0.0

    def evaluate(
        self,
        state: object,
        questions: Sequence[QuestionSpec],
    ) -> ProviderResult:
        expected = self._expected_by_state.get(str(state), {})
        answers: dict[str, Decision] = {}
        for question in questions:
            value = expected.get(question.id, self._fallback_value(question))
            answers[question.id] = Decision(
                question_id=question.id,
                value=value,
                confidence=0.75,
                predicted_probability=0.8,
            )
        return ProviderResult(
            provider=self.name,
            model="characterization-model",
            answers=answers,
            latency_ms=12.5,
            input_tokens=11,
            cached_input_tokens=2,
            output_tokens=7,
            estimated_cost_usd=0.001,
        )


def test_smoke_suite_preserves_experiment_sizes_and_primary_rows() -> None:
    frame = run_all(_OracleFakeProvider(), scaling_repeats=1)

    assert frame.groupby("experiment").size().to_dict() == {
        "01-routing": 24,
        "02-calibration": 30,
        "03-parallel-scaling": 6,
        "04-workflow": 30,
        "05-hybrid-agent": 25,
    }

    primary = frame[frame["primary_metric"].fillna(False)]
    assert primary.groupby("experiment").size().to_dict() == {
        "01-routing": 24,
        "02-calibration": 30,
        "04-workflow": 6,
        "05-hybrid-agent": 5,
    }
    assert primary["correct"].all()

    assert REQUIRED_RESULT_COLUMNS.issubset(frame.columns)
    assert frame["provider"].eq("characterization-fake").all()
    assert frame["model"].eq("characterization-model").all()
    assert frame["input_state"].map(lambda value: isinstance(value, str)).all()


def test_invalid_provider_result_collapses_to_request_level_failure() -> None:
    case = BenchmarkCase(
        case_id="case-invalid",
        state={"b": 2, "a": 1},
        expected={"department": "billing"},
        metadata={"difficulty": "fixture"},
    )
    question = QuestionSpec(
        id="department",
        type="choice",
        instructions="Route the request.",
        criteria={"billing": "Billing", "technical": "Technical"},
    )
    result = ProviderResult(
        provider="fake",
        model="fake-model",
        answers={},
        latency_ms=9.0,
        input_tokens=4,
        cached_input_tokens=1,
        output_tokens=0,
        estimated_cost_usd=0.0,
        valid=False,
        error="provider failed",
    )

    rows = _rows_for_case("01-routing", case, [question], result)

    assert rows == [
        {
            "experiment": "01-routing",
            "case_id": "case-invalid",
            "input_state": '{"a": 1, "b": 2}',
            "provider": "fake",
            "model": "fake-model",
            "question_id": "__request__",
            "expected": None,
            "actual": None,
            "correct": False,
            "confidence": None,
            "predicted_probability": None,
            "latency_ms": 9.0,
            "input_tokens": 4,
            "cached_input_tokens": 1,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "valid": False,
            "error": "provider failed",
            "primary_metric": True,
            "difficulty": "fixture",
        }
    ]


def test_missing_answer_is_a_question_level_invalid_row() -> None:
    case = BenchmarkCase(
        case_id="case-missing",
        state="billing question",
        expected={"department": "billing"},
    )
    question = QuestionSpec(
        id="department",
        type="choice",
        instructions="Route the request.",
        criteria={"billing": "Billing", "technical": "Technical"},
    )
    result = ProviderResult(
        provider="fake",
        model="fake-model",
        answers={},
        latency_ms=5.0,
        valid=True,
    )

    row = _rows_for_case("01-routing", case, [question], result)[0]

    assert row["question_id"] == "department"
    assert row["expected"] == "billing"
    assert row["actual"] is None
    assert row["correct"] is False
    assert row["valid"] is False
    assert row["error"] == "missing answer"


def test_append_results_is_append_only_for_existing_csv(tmp_path: Path) -> None:
    output = tmp_path / "results.csv"
    first = pd.DataFrame(
        [{"case_id": "first", "correct": True, "provider": "fake"}]
    )
    second = pd.DataFrame(
        [{"case_id": "second", "correct": False, "provider": "fake"}]
    )

    append_results(first, output)
    append_results(second, output)

    stored = pd.read_csv(output)
    assert stored["case_id"].tolist() == ["first", "second"]
    assert stored["correct"].tolist() == [True, False]


def test_manifest_preserves_reproducibility_contract(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_manifest(
        path,
        run_group="group-1",
        suite="smoke",
        runner_location="test-runner",
        requested_models={"korgis": ["local-model"]},
        resolved_models={"korgis": ["local-model"]},
        parameters={"seed": 42, "profile": "smoke"},
        pricing={"snapshot": "fixture"},
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert set(payload) == {
        "run_group",
        "suite",
        "created_at_utc",
        "runner_location",
        "git_commit",
        "python",
        "platform",
        "requested_models",
        "resolved_models",
        "parameters",
        "pricing",
        "packages",
    }
    assert payload["run_group"] == "group-1"
    assert payload["suite"] == "smoke"
    assert payload["runner_location"] == "test-runner"
    assert payload["requested_models"] == {"korgis": ["local-model"]}
    assert payload["resolved_models"] == {"korgis": ["local-model"]}
    assert payload["parameters"] == {"seed": 42, "profile": "smoke"}
    assert payload["pricing"] == {"snapshot": "fixture"}
