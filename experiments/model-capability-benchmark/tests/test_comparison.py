from __future__ import annotations

import pytest

from model_capability_bench.runner.comparison import paired_binary_comparison


def _case(sample_id: str, value: float):
    return {
        "state": {"metadata": {"sample_id": sample_id}},
        "evaluation": {
            "record": {
                "metrics": [{"name": "accuracy", "value": value}],
            }
        },
    }


def test_paired_binary_comparison_aligns_same_cases() -> None:
    a = [_case("1", 1), _case("2", 1), _case("3", 0), _case("4", 0)]
    b = [_case("1", 1), _case("2", 0), _case("3", 1), _case("4", 1)]

    result = paired_binary_comparison(
        a,
        b,
        metric_name="accuracy",
        practical_delta=0.20,
        bootstrap_samples=200,
        seed=7,
    )

    assert result["paired_count"] == 4
    assert result["both_correct"] == 1
    assert result["model_a_only"] == 1
    assert result["model_b_only"] == 2
    assert result["both_wrong"] == 0
    assert result["delta_b_minus_a"] == pytest.approx(0.25)
    assert result["ci95_low"] <= result["delta_b_minus_a"] <= result["ci95_high"]
    assert result["exceeds_practical_delta"] is True
    assert result["mcnemar_exact_p"] is not None


def test_paired_binary_comparison_ignores_unpaired_cases() -> None:
    result = paired_binary_comparison(
        [_case("same", 1), _case("only-a", 0)],
        [_case("same", 0), _case("only-b", 1)],
        metric_name="accuracy",
        bootstrap_samples=50,
    )
    assert result["paired_count"] == 1
    assert result["model_a_only"] == 1
    assert result["delta_b_minus_a"] == -1.0
