"""Publication contract: no proprietary Jev metrics, raw cases or invented comparisons."""
from __future__ import annotations

import json

import pytest
from scripts.publish_portfolio_summary import build_public_summary

def _row(model: str, *, provider: str = "local-korgis", requests: int = 77) -> dict:
    return {
        "model": model, "provider": provider, "requests": requests,
        "accuracy": 0.6, "latency_p50_ms": 200.0, "valid_rate": 0.9,
        "run_ids": ["secret-id"], "input_state": "private prompt",
        "expected": "private answer", "raw_cost_breakdown": {"key": "secret"},
    }


def _payload() -> dict:
    return {
        "metadata": {"api_key": "sensitive"},
        "experiments": {
            "routing": {"has_data": True, "count": 300},
            "calibration": {"has_data": True, "count": 42},
            "workflow": {"has_data": False},
        },
        "routing": {"cases": [{"input_state": "private case"}]},
        "overview": [
            _row("qwen-2b"), _row("qwen-9b"),
            _row("qwen-pilot", requests=24),
            _row("jev-v1", provider="jev"),
            _row("clm8b", provider="clm"),
            _row("typesafe-system-one", provider="llm-workflow"),
        ],
    }


def test_public_projection_contains_only_allowlisted_metrics() -> None:
    result = build_public_summary(
        _payload(), source_ref="immutable-sha", source_path="results/benchmark_data.json",
    )
    assert result["schema_version"] == 1
    assert result["routing"]["total_model_requests"] == 178
    assert result["routing"]["comparison_group"]["model_count"] == 2
    assert result["routing"]["comparison_group"]["comparability"] == "equal_request_counts_only"
    assert result["publication"]["restricted_jev_typesafe_clm_metrics_included"] is False
    serialized = json.dumps(result).lower()
    for secret in ("private prompt", "private case", "private answer", "sensitive", "secret-id", "jev-v1", "clm8b", "typesafe-system-one"):
        assert secret not in serialized


def test_unpublished_experiments_do_not_inherit_source_counts() -> None:
    result = build_public_summary(
        _payload(), source_ref="sha", source_path="results/benchmark_data.json",
    )
    statuses = {row["id"]: row for row in result["experiments"]}
    assert statuses["routing"]["status"] == "published_subset"
    assert statuses["calibration"]["status"] == "withheld_pending_review"
    assert statuses["calibration"]["published_model_count"] == 0
    assert statuses["workflow"]["status"] == "not_published"


def test_no_allowed_aggregates_fails_closed() -> None:
    with pytest.raises(ValueError, match="No publishable"):
        build_public_summary(
            {"overview": [_row("jev", provider="jev")]},
            source_ref="sha", source_path="results/benchmark_data.json",
        )


def test_invalid_metrics_and_duplicate_models_fail() -> None:
    invalid = _row("broken")
    invalid["latency_p50_ms"] = float("nan")
    with pytest.raises(ValueError, match="No publishable"):
        build_public_summary(
            {"overview": [invalid]}, source_ref="sha", source_path="p",
        )
    with pytest.raises(ValueError, match="Duplicate"):
        build_public_summary(
            {"overview": [_row("same"), _row("same")]}, source_ref="sha", source_path="p",
        )


def test_rejects_unversioned_input() -> None:
    with pytest.raises(ValueError, match="required"):
        build_public_summary(_payload(), source_ref="", source_path="p")
