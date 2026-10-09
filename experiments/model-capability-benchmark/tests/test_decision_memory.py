from __future__ import annotations

from model_capability_bench.analytics.decision_summary import (
    _summarize_model_resources,
)


def _cell(
    run_id: str,
    peak: float | None,
    *,
    completed_at: str = "2026-10-09T08:00:00Z",
    execution_signature: str = "sha256:execution:one",
    sample_count: int = 4,
) -> dict:
    return {
        "run_id": run_id,
        "execution_signature": execution_signature,
        "completed_at_utc": completed_at,
        "resource_summary": {
            "source": "korgis:/api/v1/resources",
            "scope": "owned_backend_process",
            "process_cpu_percent_avg": 120.0,
            "process_rss_bytes_avg": peak / 2 if peak else None,
            "process_rss_bytes_peak": peak,
            "system_available_memory_bytes_min": 6_000_000_000,
            "accelerator_memory_bytes_peak": 500_000_000,
            "sample_count": sample_count,
            "sampling_error_count": 0,
        },
    }


def test_peak_rss_is_attributed_to_its_own_run_not_latest_run() -> None:
    earlier = _cell(
        "run-high", 8_000_000_000,
        completed_at="2026-10-08T08:00:00Z",
        execution_signature="sha256:mac-m3",
    )
    later = _cell(
        "run-latest", 4_000_000_000,
        completed_at="2026-10-09T08:00:00Z",
        execution_signature="sha256:mac-m4",
    )
    env_m3 = {
        "run_id": "run-high", "cpu_model": "Apple M3 Pro",
        "machine": "arm64", "total_memory_bytes": 18_000_000_000,
    }
    env_m4 = {
        "run_id": "run-latest", "cpu_model": "Apple M4 Max",
        "machine": "arm64", "total_memory_bytes": 36_000_000_000,
    }
    summary = _summarize_model_resources(
        [earlier, later],
        {
            ("run-high", "sha256:mac-m3"): env_m3,
            ("run-latest", "sha256:mac-m4"): env_m4,
        },
    )
    assert summary["process_rss_bytes_peak"] == 8_000_000_000
    assert summary["peak_run_id"] == "run-high"
    assert summary["peak_execution_environment"] == env_m3
    assert summary["peak_execution_signature"] == "sha256:mac-m3"
    assert summary["process_rss_bytes_avg"] == 3_000_000_000
    assert summary["sample_count"] == 8
    assert summary["resource_cell_count"] == 2
    assert summary["system_available_memory_bytes_min"] == 6_000_000_000


def test_missing_memory_does_not_turn_into_zero_or_invent_device() -> None:
    summary = _summarize_model_resources(
        [_cell("run-api", None)],
        {},
    )
    assert summary["process_rss_bytes_peak"] is None
    assert summary["peak_run_id"] is None
    assert summary["peak_execution_environment"] is None
    assert summary["process_rss_bytes_avg"] is None


def test_empty_and_partial_telemetry_is_explicit() -> None:
    empty = _summarize_model_resources([], {})
    assert empty["process_rss_bytes_peak"] is None
    assert empty["sample_count"] == 0
    assert empty["scope"] == "unavailable"
    missing_env = _summarize_model_resources(
        [_cell("run-local", 5_000_000_000)],
        {},
    )
    assert missing_env["peak_run_id"] == "run-local"
    assert missing_env["peak_execution_environment"] is None
    assert missing_env["process_rss_bytes_peak"] == 5_000_000_000


def test_telemetry_scope_and_sample_errors_propagate() -> None:
    first = _cell("run-first", 3_000_000_000, sample_count=5)
    second = _cell("run-second", 4_000_000_000, sample_count=2)
    second["resource_summary"]["scope"] = "mixed"
    second["resource_summary"]["sampling_error_count"] = 3
    result = _summarize_model_resources([first, second], {})
    assert result["scope"] == "mixed"
    assert result["sampling_error_count"] == 3
    assert result["sample_count"] == 7
    assert result["accelerator_memory_bytes_peak"] == 500_000_000
