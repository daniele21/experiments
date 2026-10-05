from __future__ import annotations

from model_capability_bench.analytics.latest import (
    ResultCandidate,
    canonical_latest,
    result_state,
)
from model_capability_bench.observability.events import EvidenceRef, build_event
from model_capability_bench.observability.signatures import stable_signature


def test_signature_canonicalization_has_golden_value() -> None:
    signature = stable_signature(
        "fixture",
        {"a": 1, "b": ["x", 2]},
    )
    assert signature == (
        "sha256:fixture:"
        "32136f5ec73d87e455ffd9739789ef893f04cf9d85b968c0bbd2e32310dc03f3"
    )
    assert signature == stable_signature(
        "fixture",
        {"b": ["x", 2], "a": 1},
    )


def test_typed_event_keeps_report_compatibility_alias() -> None:
    event = build_event(
        "inference.completed",
        run_id="run-1",
        run_group="group",
        model_key="model",
        case_id="case-1",
        attempt=1,
        duration_ms=12.5,
        payload_ref=EvidenceRef(
            file="raw.jsonl",
            case_id="case-1",
            attempt=1,
        ),
        metadata={"run_id": "run-1"},
    )

    record = event.to_record()

    assert record["schema_version"] == "1"
    assert record["event_type"] == "inference.completed"
    assert record["event"] == "inference.completed"
    assert record["payload_ref"]["file"] == "raw.jsonl"
    assert record["duration_ms"] == 12.5


def test_latest_policy_excludes_newer_partial_run() -> None:
    older = ResultCandidate(
        run_id="run-complete",
        model_signature="model-a",
        benchmark_signature="bench-a",
        capability_id="structured-output",
        completed_at_utc="2026-10-05T08:00:00+00:00",
        status="COMPLETED",
    )
    newer_partial = ResultCandidate(
        run_id="run-partial",
        model_signature="model-a",
        benchmark_signature="bench-a",
        capability_id="structured-output",
        completed_at_utc="2026-10-05T09:00:00+00:00",
        status="PARTIAL",
    )

    latest = canonical_latest([older, newer_partial])

    assert latest[older.quality_key].run_id == "run-complete"
    assert result_state(older, current=older) == "CURRENT"
    assert result_state(newer_partial, current=older) == "PARTIAL"


def test_latest_policy_keeps_new_benchmark_lineage_separate() -> None:
    v2 = ResultCandidate(
        run_id="run-v2",
        model_signature="model-a",
        benchmark_signature="bench-v2",
        capability_id="structured-output",
        completed_at_utc="2026-10-05T08:00:00+00:00",
        status="COMPLETED",
    )
    v3 = ResultCandidate(
        run_id="run-v3",
        model_signature="model-a",
        benchmark_signature="bench-v3",
        capability_id="structured-output",
        completed_at_utc="2026-10-05T09:00:00+00:00",
        status="COMPLETED",
    )

    latest = canonical_latest([v2, v3])

    assert len(latest) == 2
    assert latest[v2.quality_key].run_id == "run-v2"
    assert latest[v3.quality_key].run_id == "run-v3"
