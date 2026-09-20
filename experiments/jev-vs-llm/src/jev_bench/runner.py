from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from pathlib import Path

import pandas as pd

from jev_bench.benchmark_data import (
    DEFAULT_CACHE,
    balanced_banking77_cases,
    banking77_question,
    calibration_public_cases,
)
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





def _serialize_state(state: object) -> str:
    if isinstance(state, str):
        return state
    return json.dumps(state, ensure_ascii=False, sort_keys=True, default=str)


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
    primary: bool = True,
) -> list[dict]:
    if not result.valid:
        return [
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "input_state": _serialize_state(case.state),
                "provider": result.provider,
                "model": result.model,
                "question_id": "__request__",
                "expected": None,
                "actual": None,
                "correct": False,
                "confidence": None,
                "predicted_probability": None,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "cached_input_tokens": result.cached_input_tokens,
                "output_tokens": result.output_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "valid": False,
                "error": result.error,
                "primary_metric": primary,
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
                    "input_state": _serialize_state(case.state),
                    "provider": result.provider,
                    "model": result.model,
                    "question_id": q.id,
                    "expected": expected,
                    "actual": None,
                    "correct": False,
                    "confidence": None,
                    "predicted_probability": None,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "valid": False,
                    "error": "missing answer",
                    "primary_metric": primary,
                    **case.metadata,
                }
            )
            continue

        output.append(
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "input_state": _serialize_state(case.state),
                "provider": result.provider,
                "model": result.model,
                "question_id": q.id,
                "expected": expected,
                "actual": decision.value,
                "correct": _correct(expected, decision.value, q),
                "confidence": decision.confidence,
                "predicted_probability": decision.predicted_probability,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "cached_input_tokens": result.cached_input_tokens,
                "output_tokens": result.output_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "valid": True,
                "error": result.error,
                "primary_metric": primary,
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
        rows.extend(_rows_for_case(experiment, case, questions, result, primary=True))
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
                    "input_state": scaling_state(),
                    "provider": result.provider,
                    "model": result.model,
                    "question_id": "__batch__",
                    "expected": None,
                    "actual": count,
                    "correct": True,
                    "confidence": None,
                    "predicted_probability": None,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "valid": result.valid,
                    "error": result.error,
                    "question_count": count,
                    "primary_metric": False,
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
        rows.extend(_rows_for_case(experiment, case, questions, result, primary=False))
        if not result.valid or any(q.id not in result.answers for q in questions):
            continue

        values = {q.id: result.answers[q.id].value for q in questions}
        action = action_fn(values, case.state) if experiment == "04-workflow" else action_fn(values)
        confidences = [
            d.confidence for d in result.answers.values() if d.confidence is not None
        ]
        probabilities = [
            d.predicted_probability
            for d in result.answers.values()
            if d.predicted_probability is not None
        ]
        rows.append(
            {
                "experiment": experiment,
                "case_id": case.case_id,
                "input_state": _serialize_state(case.state),
                "provider": result.provider,
                "model": result.model,
                "question_id": "final_action",
                "expected": case.expected["final_action"],
                "actual": action,
                "decision_trace": json.dumps(
                    {
                        "intermediate": values,
                        "final_action": action,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
                "correct": action == case.expected["final_action"],
                "confidence": min(confidences) if confidences else None,
                "predicted_probability": min(probabilities) if probabilities else None,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "cached_input_tokens": result.cached_input_tokens,
                "output_tokens": result.output_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "valid": True,
                "error": result.error,
                "primary_metric": True,
            }
        )
    return rows


def run_experiment(
    experiment: str,
    provider: DecisionProvider,
    *,
    scaling_repeats: int = 5,
) -> pd.DataFrame:
    """Run one committed smoke experiment with the shared benchmark harness."""
    key = experiment.strip().lower().replace("_", "-")
    aliases = {
        "01": "routing",
        "01-routing": "routing",
        "routing": "routing",
        "02": "calibration",
        "02-calibration": "calibration",
        "calibration": "calibration",
        "03": "scaling",
        "03-parallel-scaling": "scaling",
        "scaling": "scaling",
        "04": "workflow",
        "04-workflow": "workflow",
        "workflow": "workflow",
        "05": "agent",
        "05-hybrid-agent": "agent",
        "agent": "agent",
    }
    resolved = aliases.get(key)
    if resolved is None:
        raise ValueError(
            "experiment must be routing, calibration, scaling, workflow, or agent"
        )
    if resolved == "routing":
        rows = run_cases("01-routing", provider, routing_cases(), routing_questions())
    elif resolved == "calibration":
        rows = run_cases("02-calibration", provider, calibration_cases(), routing_questions())
    elif resolved == "scaling":
        rows = run_scaling(provider, scaling_repeats)
    elif resolved == "workflow":
        rows = run_workflow(
            "04-workflow",
            provider,
            expense_cases(),
            expense_questions(),
            _expense_action,
        )
    else:
        rows = run_workflow(
            "05-hybrid-agent",
            provider,
            support_cases(),
            support_questions(),
            _support_action,
        )
    return pd.DataFrame(rows)


def run_all(provider: DecisionProvider, scaling_repeats: int = 5) -> pd.DataFrame:
    """Run the small committed smoke suite."""
    rows = []
    rows += run_cases("01-routing", provider, routing_cases(), routing_questions())
    rows += run_cases("02-calibration", provider, calibration_cases(), routing_questions())
    rows += run_scaling(provider, scaling_repeats)
    rows += run_workflow("04-workflow", provider, expense_cases(), expense_questions(), _expense_action)
    rows += run_workflow("05-hybrid-agent", provider, support_cases(), support_questions(), _support_action)
    return pd.DataFrame(rows)


def run_public_classification(
    provider: DecisionProvider,
    *,
    cache_dir: Path = DEFAULT_CACHE,
    routing_max_cases: int | None = 770,
    calibration_in_scope: int | None = 500,
    calibration_oos: int | None = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """Run benchmark-grade public classification/calibration datasets."""
    rows = []
    routing = balanced_banking77_cases(
        cache_dir,
        max_cases=routing_max_cases,
        seed=seed,
        experiment="01-routing-public",
    )
    rows += run_cases(
        "01-routing-public",
        provider,
        routing,
        [banking77_question(cache_dir, include_other=False)],
    )

    calibration = calibration_public_cases(
        cache_dir,
        in_scope_cases=calibration_in_scope,
        oos_cases=calibration_oos,
        seed=seed,
    )
    rows += run_cases(
        "02-calibration-public",
        provider,
        calibration,
        [banking77_question(cache_dir, include_other=True)],
    )
    return pd.DataFrame(rows)


def append_results(frame: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        existing = pd.read_csv(output)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(output, index=False)


EXPENSE_POLICY = """
Every claim has one final action. If there is a clear fraud/tampering pattern, REVIEW it.
Otherwise, if the receipt is unreadable, REQUEST_RECEIPT. Otherwise, if it is a meal over
EUR 75 and the claim description does not match the receipt, MANAGER_REVIEW. Everything
else is APPROVE.
""".strip()

SUPPORT_POLICY = """
Choose one final action. If the customer explicitly requests a human or is clearly angry,
HANDOFF. Otherwise a refund request enters REFUND_FLOW; a cancellation enters CANCEL_FLOW;
an urgent technical problem enters PRIORITY_SUPPORT; everything else is ANSWER.
""".strip()


def run_monolithic_workflows(provider) -> pd.DataFrame:
    rows: list[dict] = []
    specs = [
        (
            "04-workflow",
            expense_cases(),
            EXPENSE_POLICY,
            ["approve", "manager_review", "request_receipt", "review"],
        ),
        (
            "05-hybrid-agent",
            support_cases(),
            SUPPORT_POLICY,
            ["answer", "refund_flow", "cancel_flow", "priority_support", "handoff"],
        ),
    ]
    for experiment, cases, policy, actions in specs:
        for case in cases:
            result = provider.decide(case.state, policy, actions)
            decision = result.answers.get("final_action") if result.valid else None
            actual = decision.value if decision else None
            rows.append(
                {
                    "experiment": experiment,
                    "case_id": case.case_id,
                    "input_state": _serialize_state(case.state),
                    "provider": result.provider,
                    "model": result.model,
                    "question_id": "final_action",
                    "expected": case.expected["final_action"],
                    "actual": actual,
                    "decision_trace": json.dumps(
                        {
                            "mode": "monolithic",
                            "policy": policy,
                            "final_action": actual,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    ),
                    "correct": bool(decision and actual == case.expected["final_action"]),
                    "confidence": decision.confidence if decision else None,
                    "predicted_probability": (
                        decision.predicted_probability if decision else None
                    ),
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "valid": result.valid,
                    "error": result.error,
                    "primary_metric": True,
                }
            )
    return pd.DataFrame(rows)
