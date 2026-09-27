from __future__ import annotations

from pathlib import Path

import pytest
from benchmark_core import (
    GenerationConfig,
    InferenceResult,
    Sample,
    TaskExecutionContext,
)

from model_capability_bench import build_task_registry

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks.yaml"


def _context(dataset_id: str) -> TaskExecutionContext:
    return TaskExecutionContext(
        run_id="run-1",
        dataset_id=dataset_id,
        profile="smoke",
        generation=GenerationConfig(temperature=0.0, seed=42),
    )


def test_task_catalog_builds_without_runner_task_branches() -> None:
    registry = build_task_registry(TASKS)

    assert registry.summary() == {
        "tasks": 2,
        "task_ids": ["intent-classification", "structured-output"],
        "plugins": ["intent-classification", "structured-output"],
    }


def test_intent_classification_builds_schema_from_sample_metadata() -> None:
    task = build_task_registry(TASKS).get("intent-classification")
    sample = Sample(
        sample_id="banking-1",
        input="I was charged twice.",
        expected="card_payment_fee_charged",
        metadata={
            "labels": [
                "card_payment_fee_charged",
                "cash_withdrawal",
                "cash_withdrawal_charge",
            ]
        },
    )

    request = task.build_request(sample, _context("banking77"))

    assert request.response_schema == {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "enum": [
                    "card_payment_fee_charged",
                    "cash_withdrawal",
                    "cash_withdrawal_charge",
                ],
            }
        },
        "required": ["label"],
        "additionalProperties": False,
    }
    assert request.task_metadata["task_version"] == "1"
    assert request.task_metadata["prompt_id"] == "intent-classification-v1"

    result = task.evaluate(
        sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output={"label": "card_payment_fee_charged"},
            normalized_output={"label": "card_payment_fee_charged"},
            latency_ms=2.0,
        ),
        _context("banking77"),
    )

    assert result.valid is True
    assert result.prediction == "card_payment_fee_charged"
    assert result.metrics[0].name == "accuracy"
    assert result.metrics[0].value == 1.0


def test_intent_classification_rejects_missing_label_space() -> None:
    task = build_task_registry(TASKS).get("intent-classification")
    sample = Sample(
        sample_id="invalid",
        input="hello",
        expected="greeting",
    )

    with pytest.raises(ValueError, match="labels"):
        task.build_request(sample, _context("banking77"))


def test_structured_output_uses_sample_schema_and_scores_fields() -> None:
    task = build_task_registry(TASKS).get("structured-output")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["name", "amount"],
        "additionalProperties": False,
    }
    sample = Sample(
        sample_id="extract-1",
        input="Alice paid 12.5 euros.",
        expected={"name": "Alice", "amount": 12.5},
        metadata={"response_schema": schema},
    )

    request = task.build_request(
        sample,
        _context("structured-output-controlled-v1"),
    )
    assert request.response_schema == schema

    result = task.evaluate(
        sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output={"name": "Alice", "amount": 12.5, "extra": "x"},
            normalized_output={"name": "Alice", "amount": 12.5, "extra": "x"},
            latency_ms=2.0,
        ),
        _context("structured-output-controlled-v1"),
    )

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert metrics == {
        "schema_valid_rate": 1.0,
        "field_accuracy": 1.0,
        "hallucinated_fields": 1,
    }
    assert result.valid is True


def test_registry_enforces_task_dataset_compatibility() -> None:
    registry = build_task_registry(TASKS)

    registry.validate_dataset("intent-classification", "banking77")
    with pytest.raises(ValueError, match="not compatible"):
        registry.validate_dataset(
            "intent-classification",
            "structured-output-controlled-v1",
        )
