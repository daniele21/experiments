import pandas as pd
import pytest

from jev_bench.metrics import (
    brier_score,
    calibration_summary,
    expected_calibration_error,
    macro_f1,
    summarize,
    wilson_interval,
)


def test_brier_perfect_is_zero():
    assert brier_score([1, 0], [1.0, 0.0]) == 0.0


def test_ece_perfect_is_zero():
    assert expected_calibration_error([1, 0], [1.0, 0.0], bins=2) == 0.0


def test_macro_f1_perfect_is_one():
    assert macro_f1(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_macro_f1_penalizes_minority_class_error():
    score = macro_f1(["a", "a", "a", "b"], ["a", "a", "a", "a"])
    assert 0.0 < score < 1.0


def test_wilson_interval_contains_observed_accuracy():
    low, high = wilson_interval(90, 100)
    assert low < 0.9 < high


def test_summary_uses_primary_outcome_and_request_latency():
    rows = pd.DataFrame([
        {
            "experiment": "04-workflow",
            "provider": "jev",
            "model": "x",
            "case_id": "1",
            "question_id": "q1",
            "valid": True,
            "correct": False,
            "primary_metric": False,
            "expected": "yes",
            "actual": "no",
            "confidence": 0.5,
            "predicted_probability": 0.6,
            "latency_ms": 100,
            "input_tokens": 10,
            "output_tokens": 1,
        },
        {
            "experiment": "04-workflow",
            "provider": "jev",
            "model": "x",
            "case_id": "1",
            "question_id": "final_action",
            "valid": True,
            "correct": True,
            "primary_metric": True,
            "expected": "approve",
            "actual": "approve",
            "confidence": 0.8,
            "predicted_probability": 0.9,
            "latency_ms": 100,
            "input_tokens": 10,
            "output_tokens": 1,
        },
    ])
    out = summarize(rows).iloc[0]
    assert out["accuracy"] == 1.0
    assert out["intermediate_accuracy"] == 0.0
    assert out["latency_p50_ms"] == 100.0


def test_calibration_uses_predicted_probability_not_native_confidence():
    rows = pd.DataFrame([
        {
            "experiment": "02-calibration-public",
            "provider": "jev",
            "model": "x",
            "case_id": "1",
            "question_id": "intent",
            "valid": True,
            "correct": True,
            "primary_metric": True,
            "expected": "a",
            "actual": "a",
            "confidence": 0.1,
            "predicted_probability": 1.0,
        },
        {
            "experiment": "02-calibration-public",
            "provider": "jev",
            "model": "x",
            "case_id": "2",
            "question_id": "intent",
            "valid": True,
            "correct": False,
            "primary_metric": True,
            "expected": "b",
            "actual": "a",
            "confidence": 0.9,
            "predicted_probability": 0.0,
        },
    ])
    result = calibration_summary(rows).iloc[0]
    assert result["brier_probability"] == pytest.approx(0.0)
    assert result["mean_confidence"] == pytest.approx(0.5)
