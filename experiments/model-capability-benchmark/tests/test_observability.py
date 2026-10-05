from __future__ import annotations

from types import SimpleNamespace

from benchmark_core import CapabilityComparisonSpec, CapabilityMetricSpec

from model_capability_bench.analytics.latest import (
    ResultCandidate,
    canonical_latest,
    result_state,
)
from model_capability_bench.observability.events import EvidenceRef, build_event
from model_capability_bench.observability.signatures import (
    benchmark_signature,
    execution_signature,
    stable_signature,
)


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


def test_execution_signature_changes_with_hardware_identity() -> None:
    model = SimpleNamespace(
        runtime=SimpleNamespace(
            runtime_key="korgis-local",
            deployment="local",
            lifecycle="managed",
            options={"ctx_size": 8192},
        ),
        provider=SimpleNamespace(
            provider_key="korgis",
            provider_type="openai-compatible",
            options={},
        ),
    )
    common = {
        "system": "darwin",
        "release": "25.0",
        "machine": "arm64",
        "total_memory_bytes": 36 * 1024**3,
    }

    m3 = execution_signature(
        model,
        execution_environment={**common, "cpu_model": "Apple M3 Pro"},
    )
    m4 = execution_signature(
        model,
        execution_environment={**common, "cpu_model": "Apple M4 Pro"},
    )

    assert m3 != m4
    assert m3 == execution_signature(
        model,
        execution_environment={**common, "cpu_model": "Apple M3 Pro"},
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


def test_benchmark_signature_ignores_practical_delta_but_tracks_metric_semantics() -> None:
    loaded = {
        "dataset": SimpleNamespace(
            spec=SimpleNamespace(
                version="1",
                revision="rev-1",
                split="test",
            ),
            selection_fingerprint="sha256:selection",
            source_checksums={"source": "abc"},
        )
    }
    task = SimpleNamespace(
        spec=SimpleNamespace(
            task_id="task",
            version="2",
            prompt_id="prompt",
            prompt_version="1",
            evaluator_id="eval",
            evaluator_version="2",
        )
    )

    def capability(practical_delta: float, reducer: str = "mean"):
        return SimpleNamespace(
            spec=SimpleNamespace(
                capability_id="cap",
                dataset_ids=("dataset",),
                metrics=(
                    CapabilityMetricSpec(
                        name="accuracy",
                        source="task_metric",
                        reducer=reducer,
                        field="accuracy",
                        primary=True,
                    ),
                ),
                context_bindings=(),
                options={},
                comparison=CapabilityComparisonSpec(
                    metric="accuracy",
                    practical_delta=practical_delta,
                ),
            )
        )

    first = benchmark_signature(
        suite_id="suite",
        suite_version="2",
        capability=capability(0.03),
        task=task,
        loaded_datasets=loaded,
        profile_id="core",
        generation={"temperature": 0},
        seed=42,
    )
    changed_threshold = benchmark_signature(
        suite_id="suite",
        suite_version="2",
        capability=capability(0.10),
        task=task,
        loaded_datasets=loaded,
        profile_id="core",
        generation={"temperature": 0},
        seed=42,
    )
    changed_reducer = benchmark_signature(
        suite_id="suite",
        suite_version="2",
        capability=capability(0.03, reducer="rate"),
        task=task,
        loaded_datasets=loaded,
        profile_id="core",
        generation={"temperature": 0},
        seed=42,
    )

    assert first == changed_threshold
    assert first != changed_reducer
