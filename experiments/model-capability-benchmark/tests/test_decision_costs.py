from __future__ import annotations

import pytest

from model_capability_bench.analytics.decision_summary import _aggregate_case_metrics


def _case(cost: float | None) -> dict[str, object]:
    return {
        "latency_ms": 100.0,
        "estimated_cost_usd": cost,
        "inference_valid": True,
        "evaluation_valid": True,
        "input_tokens": 100,
        "output_tokens": 20,
    }


def test_complete_api_cost_coverage() -> None:
    result = _aggregate_case_metrics(
        [_case(0.001), _case(0.003)],
        deployment="api",
    )

    assert result["provider_cost_status"] == "complete"
    assert result["provider_cost_known"] is True
    assert result["provider_cost_priced_cases"] == 2
    assert result["provider_cost_total_cases"] == 2
    assert result["provider_cost_coverage_rate"] == pytest.approx(1.0)
    assert result["provider_cost_total_usd"] == pytest.approx(0.004)
    assert result["provider_cost_per_case_usd"] == pytest.approx(0.002)
    assert result["provider_cost_per_1k_cases_usd"] == pytest.approx(2.0)


def test_partial_api_cost_remains_visible_with_coverage() -> None:
    result = _aggregate_case_metrics(
        [_case(0.001), _case(None), _case(0.003)],
        deployment="api",
    )

    assert result["provider_cost_status"] == "partial"
    assert result["provider_cost_known"] is True
    assert result["provider_cost_priced_cases"] == 2
    assert result["provider_cost_total_cases"] == 3
    assert result["provider_cost_coverage_rate"] == pytest.approx(2 / 3)
    assert result["provider_cost_total_usd"] == pytest.approx(0.004)
    assert result["provider_cost_per_case_usd"] == pytest.approx(0.002)
    assert result["provider_cost_per_1k_cases_usd"] == pytest.approx(2.0)


def test_unpriced_api_cost_is_unavailable_not_zero() -> None:
    result = _aggregate_case_metrics(
        [_case(None), _case(None)],
        deployment="api",
    )

    assert result["provider_cost_status"] == "unavailable"
    assert result["provider_cost_known"] is False
    assert result["provider_cost_priced_cases"] == 0
    assert result["provider_cost_total_cases"] == 2
    assert result["provider_cost_coverage_rate"] == pytest.approx(0.0)
    assert result["provider_cost_total_usd"] is None
    assert result["provider_cost_per_1k_cases_usd"] is None


def test_local_provider_cost_is_not_api_cost_even_if_zero_is_recorded() -> None:
    result = _aggregate_case_metrics(
        [_case(0.0), _case(0.0)],
        deployment="local",
    )

    assert result["provider_cost_status"] == "local_not_applicable"
    assert result["provider_cost_known"] is False
    assert result["provider_cost_priced_cases"] == 2
    assert result["provider_cost_total_cases"] == 2
    assert result["provider_cost_total_usd"] is None
    assert result["provider_cost_per_1k_cases_usd"] is None
