from __future__ import annotations

import pytest
from benchmark_core import CapabilityMetricSpec

from model_capability_bench.runner.aggregation import reduce_metric


def _evidence(
    expected,
    prediction,
    *,
    confidence: float,
    correct: bool,
    valid: bool = True,
    latency_ms: float = 10.0,
):
    return {
        "state": {"metadata": {"dataset_id": "dataset"}},
        "raw": {
            "record": {
                "valid": valid,
                "latency_ms": latency_ms,
                "input_tokens": 10,
                "output_tokens": 2,
                "estimated_cost_usd": 0.01,
            }
        },
        "evaluation": {
            "record": {
                "expected": expected,
                "prediction": prediction,
                "metrics": [
                    {"name": "confidence", "value": confidence},
                    {"name": "correct", "value": correct},
                    {
                        "name": "accuracy",
                        "value": float(expected == prediction),
                    },
                ],
            }
        },
    }


def test_quality_and_calibration_reducers() -> None:
    evidence = [
        _evidence("a", "a", confidence=0.8, correct=True),
        _evidence("a", "b", confidence=0.6, correct=False),
        _evidence("b", "b", confidence=0.9, correct=True),
        _evidence("other", "other", confidence=0.7, correct=True),
    ]

    macro_f1 = reduce_metric(
        CapabilityMetricSpec(
            name="macro_f1",
            source="evaluation",
            reducer="macro_f1",
            primary=True,
        ),
        evidence,
    )
    oos = reduce_metric(
        CapabilityMetricSpec(
            name="oos",
            source="evaluation",
            reducer="oos_detection",
            primary=True,
            options={"oos_label": "other"},
        ),
        evidence,
    )
    in_scope = reduce_metric(
        CapabilityMetricSpec(
            name="in_scope",
            source="evaluation",
            reducer="in_scope_accuracy",
            primary=True,
            options={"oos_label": "other"},
        ),
        evidence,
    )
    ece = reduce_metric(
        CapabilityMetricSpec(
            name="ece",
            source="evaluation",
            reducer="ece",
            primary=True,
            options={
                "confidence_metric": "confidence",
                "correctness_metric": "correct",
                "bins": 10,
            },
        ),
        evidence,
    )

    assert macro_f1 == pytest.approx(7 / 9)
    assert oos == 1.0
    assert in_scope == pytest.approx(2 / 3)
    assert ece == pytest.approx(0.30)


def test_inference_reducers_and_task_metric_mean() -> None:
    evidence = [
        _evidence("a", "a", confidence=0.9, correct=True, latency_ms=10),
        _evidence(
            "a",
            None,
            confidence=0.2,
            correct=False,
            valid=False,
            latency_ms=30,
        ),
        _evidence("b", "b", confidence=0.8, correct=True, latency_ms=50),
    ]

    accuracy = reduce_metric(
        CapabilityMetricSpec(
            name="accuracy",
            source="task_metric",
            reducer="mean",
            primary=True,
        ),
        evidence,
    )
    invalid_rate = reduce_metric(
        CapabilityMetricSpec(
            name="invalid",
            source="inference",
            reducer="invalid_rate",
            field="valid",
            primary=True,
        ),
        evidence,
    )
    p50 = reduce_metric(
        CapabilityMetricSpec(
            name="latency",
            source="inference",
            reducer="p50",
            field="latency_ms",
            primary=True,
        ),
        evidence,
    )
    p95 = reduce_metric(
        CapabilityMetricSpec(
            name="latency",
            source="inference",
            reducer="p95",
            field="latency_ms",
            primary=True,
        ),
        evidence,
    )
    output_tokens = reduce_metric(
        CapabilityMetricSpec(
            name="tokens",
            source="inference",
            reducer="mean",
            field="usage.output_tokens",
            primary=True,
        ),
        evidence,
    )

    assert accuracy == pytest.approx(2 / 3)
    assert invalid_rate == pytest.approx(1 / 3)
    assert p50 == 30
    assert p95 == pytest.approx(48)
    assert output_tokens == 2
