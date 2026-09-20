from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from jev_bench.datasets import (
    calibration_cases,
    expense_cases,
    expense_questions,
    routing_cases,
    routing_questions,
    scaling_question_bank,
    scaling_state,
    support_cases,
    support_questions,
)
from jev_bench.models import BenchmarkCase, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


def _binary_prediction(value: str | float) -> int:
    return int(float(value) >= 0.5)


def _correct(expected: str | float, actual: str | float, question: QuestionSpec) -> bool:
    if question.type == "noul":
        return _binary_prediction(actual) == _binary_prediction(expected)
    if question.type == "score":
        return abs(float(actual) - float(expected)) <= 0.5
    return str(actual) == str(expected)


def _rows_for_case(
    experiment: str,
    case: BenchmarkCase,
    questions: Sequence[QuestionSpec],
    result: ProviderResult,
) -> list[dict]:
    if not result.valid:
        return [
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "provider": result.provider,
                "model": result.model,
                "question_id": "__request__",
                "expected": None,
                "actual": None,
                "correct": False,
                "confidence": None,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "valid": False,
                "error": result.error,
                **case.metadata,
            }
        ]
    output = []
    for q in questions:
        expected = case.expected.get(q.id)
        decision = result.answers.get(q.id)
        if decision is None:
            output.append(
                {
                    "experiment": experiment,
                    "case_id": case.case_id,
                    "provider": result.provider,
                    "model": result.model,
                    "question_id": q.id,
                    "expected": expected,
                    "actual": None,
                    "correct": False,
                    "confidence": None,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "valid": False,
                    "error": "missing answer",
                    **case.metadata,
                }
            )
            continue
        output.append(
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "provider": result.provider,
                "model": result.model,
                "question_id": q.id,
                "expected": expected,
                "actual": decision.value,
                "correct": _correct(expected, decision.value, q),
                "confidence": decision.confidence,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "valid": True,
                "error": result.error,
                **case.metadata,
            }
        )
    return output


def run_cases(
    experiment: str,
    provider: DecisionProvider,
    cases: Sequence[BenchmarkCase],
    questions: Sequence[QuestionSpec],
) -> list[dict]:
    rows = []
    for case in cases:
        result = provider.evaluate(case.state, questions)
        rows.extend(_rows_for_case(experiment, case, questions, result))
    return rows


def run_scaling(provider: DecisionProvider, repeats: int = 5) -> list[dict]:
    rows = []
    bank = scaling_question_bank()
    for count in [1, 2, 4, 8, 16, 32]:
        questions = bank[:count]
        for repeat in range(repeats):
            result = provider.evaluate(scaling_state(), questions)
            rows.append(
                {
                    "experiment": "03-parallel-scaling",
                    "case_id": f"q{count}-r{repeat}",
                    "provider": result.provider,
                    "model": result.model,
                    "question_id": "__batch__",
                    "expected": None,
                    "actual": count,
                    "correct": True,
                    "confidence": None,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "valid": result.valid,
                    "error": result.error,
                    "question_count": count,
                }
            )
    return rows


def _expense_action(answer: dict[str, object], state: str) -> str:
    if float(answer["fraud_pattern"]) >= 0.5:
        return "review"
    if float(answer["receipt_readable"]) < 0.5:
        return "request_receipt"
    if answer["category"] == "meal" and "€110" in state and float(answer["description_matches"]) < 0.5:
        return "manager_review"
    return "approve"


def _support_action(answer: dict[str, object]) -> str:
    if float(answer["human_requested"]) >= 0.5 or float(answer["angry"]) >= 0.5:
        return "handoff"
    if answer["intent"] == "refund":
        return "refund_flow"
    if answer["intent"] == "cancel":
        return "cancel_flow"
    if answer["intent"] == "technical" and float(answer["urgent"]) >= 0.5:
        return "priority_support"
    return "answer"


def run_workflow(
    experiment: str,
    provider: DecisionProvider,
    cases: Sequence[BenchmarkCase],
    questions: Sequence[QuestionSpec],
    action_fn: Callable,
) -> list[dict]:
    rows = []
    for case in cases:
        result = provider.evaluate(case.state, questions)
        rows.extend(_rows_for_case(experiment, case, questions, result))
        if not result.valid or any(q.id not in result.answers for q in questions):
            continue
        values = {q.id: result.answers[q.id].value for q in questions}
        action = action_fn(values, case.state) if experiment == "04-workflow" else action_fn(values)
        rows.append(
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "provider": result.provider,
                "model": result.model,
                "question_id": "final_action",
                "expected": case.expected["final_action"],
                "actual": action,
                "correct": action == case.expected["final_action"],
                "confidence": min(
                    [d.confidence for d in result.answers.values() if d.confidence is not None],
                    default=None,
                ),
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "valid": True,
                "error": result.error,
            }
        )
    return rows


def run_all(provider: DecisionProvider, scaling_repeats: int = 5) -> pd.DataFrame:
    rows = []
    rows += run_cases("01-routing", provider, routing_cases(), routing_questions())
    rows += run_cases("02-calibration", provider, calibration_cases(), routing_questions())
    rows += run_scaling(provider, scaling_repeats)
    rows += run_workflow("04-workflow", provider, expense_cases(), expense_questions(), _expense_action)
    rows += run_workflow("05-hybrid-agent", provider, support_cases(), support_questions(), _support_action)
    return pd.DataFrame(rows)


def append_results(frame: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = pd.read_csv(output)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(output, index=False)
