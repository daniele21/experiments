import pytest

from jev_bench.costs import estimate_cost_usd, pricing_metadata


def test_jev_cost_uses_input_only():
    cost = estimate_cost_usd(
        provider="jev",
        model="jev-1.13.0",
        input_tokens=1_000_000,
        output_tokens=10_000,
    )
    assert cost == pytest.approx(0.042)


def test_luna_cost_includes_cached_and_output_tokens():
    cost = estimate_cost_usd(
        provider="llm-workflow",
        model="gpt-5.6-luna",
        input_tokens=1_000_000,
        cached_input_tokens=500_000,
        output_tokens=100_000,
    )
    expected = (500_000 * 0.20 + 500_000 * 0.02 + 100_000 * 1.20) / 1_000_000
    assert cost == pytest.approx(expected)


def test_unknown_model_has_no_invented_price():
    assert (
        estimate_cost_usd(
            provider="llm-workflow",
            model="unknown-model",
            input_tokens=100,
            output_tokens=10,
        )
        is None
    )


def test_pricing_snapshot_is_dated():
    pricing = pricing_metadata()
    assert pricing["as_of"] == "2026-09-20"
    assert "gpt-5.6-sol" in pricing["prices_per_million_tokens"]
