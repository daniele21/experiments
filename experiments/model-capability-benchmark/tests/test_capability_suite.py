from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmark_core import (
    DatasetLoadContext,
    InferenceResult,
    Sample,
    TaskExecutionContext,
    resolve_capability_context,
)
from model_capability_bench import load_capability_suite

ROOT = Path(__file__).resolve().parents[1]


def _write_banking_fixture(cache_dir: Path) -> None:
    banking = cache_dir / "banking77"
    banking.mkdir(parents=True, exist_ok=True)
    (banking / "categories.json").write_text(
        json.dumps(["cash_withdrawal", "card_payment", "refund"]),
        encoding="utf-8",
    )
    (banking / "test.csv").write_text(
        "text,category\n"
        "Cash withdrawal,cash_withdrawal\n"
        "Card payment,card_payment\n"
        "Refund,refund\n",
        encoding="utf-8",
    )


def test_real_suite_composes_five_capabilities_and_four_task_families() -> None:
    bundle = load_capability_suite(ROOT)

    assert bundle.suite.suite_id == "capability-core"
    assert bundle.suite.version == "1"
    assert len(bundle.resolved_capabilities) == 5
    assert {
        capability.spec.capability_id
        for capability in bundle.resolved_capabilities
    } == {
        "intent-classification",
        "oos-calibration",
        "structured-output",
        "qa-abstention",
        "mathematical-reasoning",
    }
    assert {
        capability.spec.task_id
        for capability in bundle.resolved_capabilities
    } == {
        "intent-classification",
        "calibrated-intent-classification",
        "structured-output",
        "qa-abstention",
        "mathematical-reasoning",
    }


def test_suite_plans_multiple_models_and_capabilities_without_runner_branches() -> None:
    bundle = load_capability_suite(ROOT)
    models = ["qwen3.5-2b-q4km", "gpt-5.6-luna"]

    arms = bundle.plan_matrix(model_keys=models)

    assert len(arms) == 12
    assert {arm.model_key for arm in arms} == set(models)
    assert {
        (arm.capability_id, arm.dataset_id)
        for arm in arms
    } == {
        ("intent-classification", "banking77"),
        ("oos-calibration", "banking77"),
        ("oos-calibration", "clinc150-oos"),
        ("structured-output", "structured-output-controlled-v1"),
        ("qa-abstention", "qa-abstention-controlled-v1"),
        ("mathematical-reasoning", "math-reasoning-controlled-v1"),
    }


def test_calibration_context_resolves_banking_label_space_for_clinc(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    _write_banking_fixture(tmp_path)
    profile = bundle.profiles["full"]
    banking = bundle.datasets.load(
        "banking77",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )
    capability = next(
        item.spec
        for item in bundle.resolved_capabilities
        if item.spec.capability_id == "oos-calibration"
    )
    context_metadata = resolve_capability_context(
        capability,
        {"banking77": banking},
    )

    assert context_metadata["labels"] == (
        "cash_withdrawal",
        "card_payment",
        "refund",
    )

    task = bundle.tasks.get("calibrated-intent-classification")
    sample = Sample(
        sample_id="clinc-oos",
        input="What is the weather tomorrow?",
        expected="other",
        metadata={"oos": True},
    )
    context = TaskExecutionContext(
        run_id="run-1",
        dataset_id="clinc150-oos",
        profile="full",
        generation=bundle.suite.generation,
        metadata=context_metadata,
    )
    request = task.build_request(sample, context)

    label_enum = request.response_schema["properties"]["label"]["enum"]
    assert label_enum == [
        "cash_withdrawal",
        "card_payment",
        "refund",
        "other",
    ]

    result = task.evaluate(
        sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output={"label": "other", "confidence": 0.8},
            normalized_output={"label": "other", "confidence": 0.8},
            latency_ms=1.0,
        ),
        context,
    )
    metrics = {metric.name: metric.value for metric in result.metrics}

    assert result.valid is True
    assert metrics["accuracy"] == 1.0
    assert metrics["oos_correct"] == 1.0
    assert metrics["brier_correctness_component"] == pytest.approx(0.04)


def test_qa_and_math_controlled_datasets_execute_task_contracts(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    profile = bundle.profiles["full"]

    qa_data = bundle.datasets.load(
        "qa-abstention-controlled-v1",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )
    math_data = bundle.datasets.load(
        "math-reasoning-controlled-v1",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )

    assert len(qa_data.samples) == 10
    assert len(math_data.samples) == 10

    qa_task = bundle.tasks.get("qa-abstention")
    qa_sample = qa_data.samples[0]
    qa_context = TaskExecutionContext(
        run_id="run-qa",
        dataset_id="qa-abstention-controlled-v1",
        profile="full",
        generation=bundle.suite.generation,
    )
    qa_result = qa_task.evaluate(
        qa_sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output={"answer": "Elena", "abstain": False},
            normalized_output={"answer": "Elena", "abstain": False},
            latency_ms=1.0,
        ),
        qa_context,
    )
    qa_metrics = {metric.name: metric.value for metric in qa_result.metrics}
    assert qa_metrics["exact_match"] == 1.0
    assert qa_metrics["answerability_accuracy"] == 1.0

    math_task = bundle.tasks.get("mathematical-reasoning")
    math_sample = math_data.samples[0]
    math_context = TaskExecutionContext(
        run_id="run-math",
        dataset_id="math-reasoning-controlled-v1",
        profile="full",
        generation=bundle.suite.generation,
    )
    math_result = math_task.evaluate(
        math_sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output={"answer": "25.0"},
            normalized_output={"answer": "25.0"},
            latency_ms=1.0,
        ),
        math_context,
    )
    math_metrics = {metric.name: metric.value for metric in math_result.metrics}
    assert math_metrics["final_answer_accuracy"] == 1.0
    assert math_metrics["parse_valid"] == 1.0


def test_every_capability_has_one_primary_metric_and_versioned_task() -> None:
    bundle = load_capability_suite(ROOT)

    for capability in bundle.resolved_capabilities:
        assert sum(metric.primary for metric in capability.spec.metrics) == 1
        task = bundle.tasks.get(capability.spec.task_id)
        assert task.spec.version
        assert task.spec.evaluator_version
        assert task.spec.prompt_id
        assert task.spec.prompt_version
