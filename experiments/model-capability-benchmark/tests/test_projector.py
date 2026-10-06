from __future__ import annotations

import json
from pathlib import Path

import duckdb

from model_capability_bench.analytics.dashboard_export import export_dashboard_data
from model_capability_bench.analytics.projector import project_results
from model_capability_bench.sharing.snapshot import create_share_snapshot


def _append(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _write_run(
    results_root: Path,
    *,
    run_id: str,
    completed_at: str,
    score: float,
    status: str = "COMPLETED",
    benchmark_signature: str = "sha256:benchmark:fixture-v2",
    model_key: str = "model-a",
    model_signature: str = "sha256:model:model-a",
    deployment: str = "local",
    estimated_cost_usd: float | None = None,
    latency_ms: float = 100.0,
) -> Path:
    run_dir = results_root / "runs" / run_id
    run_dir.mkdir(parents=True)
    completed = 1 if status == "COMPLETED" else 0
    failed = 0 if status == "COMPLETED" else 1
    manifest = {
        "schema_version": "1",
        "git_commit": "fixture-commit",
        "created_at_utc": completed_at,
        "run": {
            "run_id": run_id,
            "run_group": "fixture",
            "planned_cases": 1,
            "completed_cases": completed,
            "failed_cases": failed,
            "skipped_cases": 0,
            "model_failures": 0,
            "aggregate_count": 1,
            "metadata": {
                "signatures": {
                    "models": {model_key: model_signature},
                    "executions": {model_key: "sha256:execution:machine-a"},
                    "benchmarks": {
                        "structured-output": benchmark_signature,
                    },
                    "execution_environment": {
                        "system": "darwin",
                        "release": "fixture",
                        "machine": "arm64",
                        "cpu_model": "Fixture CPU",
                        "total_memory_bytes": 18_000_000_000,
                    },
                }
            },
        },
        "suite": {
            "suite_id": "capability-core",
            "version": "2",
            "profile": "core",
            "seed": 42,
        },
        "models": [
            {
                "model_key": model_key,
                "model_id": "vendor/" + model_key,
                "effective_model_id": model_key,
                "runtime_key": "runtime-a",
                "provider_key": "provider-a",
                "deployment": deployment,
                "model_signature": model_signature,
                "execution_signature": "sha256:execution:machine-a",
            }
        ],
        "capabilities": [
            {
                "capability_id": "structured-output",
                "task_id": "structured-output",
                "dataset_ids": ["structured-output-controlled-v2"],
                "benchmark_signature": benchmark_signature,
                "comparison": {
                    "metric": "exact_match",
                    "practical_delta": 0.05,
                },
                "metrics": [
                    {
                        "name": "exact_match",
                        "source": "task_metric",
                        "reducer": "mean",
                        "field": "exact_match",
                        "primary": True,
                    }
                ],
            }
        ],
        "signatures": {
            "models": {model_key: model_signature},
            "executions": {model_key: "sha256:execution:machine-a"},
            "benchmarks": {"structured-output": benchmark_signature},
            "execution_environment": {
                "system": "darwin",
                "release": "fixture",
                "machine": "arm64",
                "cpu_model": "Fixture CPU",
                "total_memory_bytes": 18_000_000_000,
            },
        },
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    if deployment == "api":
        (run_dir / "environment.json").write_text(
            json.dumps(
                {
                    "pricing": {
                        "currency": "USD",
                        "as_of": "2026-09-20",
                        "processing": "standard",
                        "prices_per_million_tokens": {
                            model_key: {
                                "match": "exact",
                                "input": 1.0,
                                "output": 1.0,
                                "source": "Fixture frozen pricing",
                                "source_url": "https://example.com/pricing",
                            }
                        },
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    _append(
        run_dir / "aggregates.jsonl",
        {
            "run_id": run_id,
            "model_key": model_key,
            "capability_id": "structured-output",
            "metric": "exact_match",
            "value": score,
            "sample_count": completed,
            "failure_count": failed,
            "primary": True,
        },
    )
    _append(
        run_dir / "report_index.jsonl",
        {
            "run_id": run_id,
            "model_key": model_key,
            "capability_id": "structured-output",
            "task_id": "structured-output",
            "profile": "core",
            "cases": (
                [{"case_id": "case-1", "attempt": 1}]
                if status == "COMPLETED"
                else []
            ),
            "dataset_ids": ["structured-output-controlled-v2"],
            "failure_count": failed,
        },
    )
    if status == "COMPLETED":
        metadata = {
            "run_id": run_id,
            "model_key": model_key,
            "model_signature": model_signature,
            "execution_signature": "sha256:execution:machine-a",
            "benchmark_signature": benchmark_signature,
            "capability_id": "structured-output",
            "dataset_id": "structured-output-controlled-v2",
            "sample_id": "sample-1",
            "case_family": "adversarial",
            "difficulty": "hard",
        }
        _append(
            run_dir / "raw.jsonl",
            {
                "case_id": "case-1",
                "attempt": 1,
                "metadata": metadata,
                "record": {
                    "run_id": run_id,
                    "valid": True,
                    "latency_ms": latency_ms,
                    "input_tokens": 20,
                    "output_tokens": 5,
                    "estimated_cost_usd": estimated_cost_usd,
                },
            },
        )
        _append(
            run_dir / "evaluation.jsonl",
            {
                "case_id": "case-1",
                "attempt": 1,
                "metadata": metadata,
                "record": {
                    "run_id": run_id,
                    "valid": True,
                    "metrics": [
                        {
                            "name": "exact_match",
                            "value": float(score >= 0.5),
                            "primary": True,
                        }
                    ],
                },
            },
        )
        _append(
            run_dir / "resource_summary.jsonl",
            {
                "case_id": "case-1",
                "attempt": 1,
                "metadata": {
                    **metadata,
                    "runtime_key": "runtime-a",
                },
                "summary": {
                    "source": "korgis:/api/v1/resources",
                    "scope": "owned_backend_process",
                    "sample_count": 4,
                    "sample_interval_ms": 250.0,
                    "process_cpu_percent_avg": 125.0,
                    "process_rss_bytes_avg": 1_000_000_000.0,
                    "process_rss_bytes_peak": 1_200_000_000.0,
                    "system_available_memory_bytes_min": 8_000_000_000.0,
                    "accelerator_memory_bytes_peak": None,
                    "sampling_error_count": 0,
                },
            },
        )
    _append(
        run_dir / "events.jsonl",
        {
            "schema_version": "1",
            "event_id": f"event-{run_id}",
            "event_type": (
                "run.completed" if status == "COMPLETED" else "case.failed"
            ),
            "event": (
                "run.completed" if status == "COMPLETED" else "case.failed"
            ),
            "timestamp_utc": completed_at,
            "run_id": run_id,
            "metadata": {"run_id": run_id},
        },
    )
    return run_dir


def test_projector_selects_latest_completed_comparable_result(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-old",
        completed_at="2026-10-05T08:00:00+00:00",
        score=0.70,
    )
    _write_run(
        results,
        run_id="run-current",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.80,
    )
    _write_run(
        results,
        run_id="run-newer-partial",
        completed_at="2026-10-05T10:00:00+00:00",
        score=0.95,
        status="PARTIAL",
    )

    summary = project_results(results_root=results, rebuild=True)

    assert summary.projected_runs == 3
    connection = duckdb.connect(summary.database_path, read_only=True)
    try:
        current = connection.execute(
            """
            SELECT run_id, primary_value
            FROM v_current_quality_results
            WHERE capability_id = 'structured-output'
            """
        ).fetchall()
        history = connection.execute(
            """
            SELECT run_id, result_state
            FROM v_model_history
            ORDER BY run_id
            """
        ).fetchall()
    finally:
        connection.close()

    assert current == [("run-current", 0.8)]
    assert ("run-current", "CURRENT") in history
    assert ("run-old", "HISTORICAL") in history
    assert ("run-newer-partial", "PARTIAL") in history

    incremental = project_results(results_root=results)
    assert incremental.projected_runs == 0
    assert incremental.skipped_runs == 3


def test_projector_keeps_changed_benchmark_lineage_separate(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-v2",
        completed_at="2026-10-05T08:00:00+00:00",
        score=0.80,
        benchmark_signature="sha256:benchmark:v2",
    )
    _write_run(
        results,
        run_id="run-v3",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.90,
        benchmark_signature="sha256:benchmark:v3",
    )

    summary = project_results(results_root=results, rebuild=True)

    connection = duckdb.connect(summary.database_path, read_only=True)
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM v_current_quality_results"
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 2


def test_dashboard_export_reads_current_projection(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-current",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.80,
    )
    summary = project_results(results_root=results, rebuild=True)
    output = results / "analytics" / "dashboard"

    exported = export_dashboard_data(
        database_path=Path(summary.database_path),
        output_dir=output,
    )

    overview = json.loads(Path(exported["overview"]).read_text())
    assert overview["capabilities"] == ["structured-output"]
    assert overview["cells"][0]["primary_value"] == 0.8
    assert overview["models"][0]["model_key"] == "model-a"
    resources = overview["cells"][0]["resource_summary"]
    assert resources["scope"] == "owned_backend_process"
    assert resources["process_cpu_percent_avg"] == 125.0
    assert resources["process_rss_bytes_peak"] == 1_200_000_000.0
    decision = overview["decision"]
    assert decision["quality_policy"]["quality_policy_id"] == "core-quality-v1"
    assert decision["model_summaries"][0]["overall_quality_score"] == 80.0
    assert decision["model_summaries"][0]["latency_p50_ms"] == 100.0
    assert decision["model_summaries"][0]["provider_cost_status"] == (
        "local_not_applicable"
    )
    assert decision["model_summaries"][0]["provider_cost_known"] is False
    assert decision["model_summaries"][0]["provider_cost_total_usd"] is None
    assert decision["dataset_summaries"][0]["dataset_id"] == (
        "structured-output-controlled-v2"
    )
    assert decision["model_summaries"][0]["execution_environment"]["cpu_model"] == (
        "Fixture CPU"
    )

    index = json.loads((output / "index.json").read_text())
    model_file = output / index["models"]["sha256:model:model-a"]
    run_file = output / index["runs"]["run-current"]
    model_payload = json.loads(model_file.read_text())
    run_payload = json.loads(run_file.read_text())

    assert model_payload["model_signature"] == "sha256:model:model-a"
    assert model_payload["current_cells"][0]["primary_value"] == 0.8
    assert model_payload["history"][0]["result_state"] == "CURRENT"
    assert run_payload["run"]["run_id"] == "run-current"
    assert run_payload["timeline"][0]["event_type"] == "run.completed"
    assert run_payload["resources"][0]["model_key"] == "model-a"
    assert run_payload["resources"][0]["sample_count"] == 4



def test_decision_overview_projects_artifact_size_and_size_pareto(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-sized-model",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.82,
        model_key="qwen3.5-9b-q4km",
        model_signature="sha256:model:qwen9-size-fixture",
        deployment="local",
    )
    summary = project_results(results_root=results, rebuild=True)
    output = results / "analytics" / "dashboard"

    exported = export_dashboard_data(
        database_path=Path(summary.database_path),
        output_dir=output,
    )

    overview = json.loads(Path(exported["overview"]).read_text())
    model = overview["decision"]["model_summaries"][0]

    assert model["artifact_size_bytes"] > 0
    assert model["observed_quality_artifact_size_pareto"] is True



def test_share_snapshot_freezes_comparable_current_results(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-model-a",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.70,
        model_key="model-a",
        model_signature="sha256:model:model-a",
    )
    _write_run(
        results,
        run_id="run-model-b",
        completed_at="2026-10-05T09:05:00+00:00",
        score=0.90,
        model_key="model-b",
        model_signature="sha256:model:model-b",
    )
    summary = project_results(results_root=results, rebuild=True)

    snapshot = create_share_snapshot(
        results_root=results,
        database_path=Path(summary.database_path),
        capability_id="structured-output",
        model_keys=("model-a", "model-b"),
        title="Local vs API structured output",
    )

    payload = json.loads(Path(snapshot.snapshot_path).read_text())
    assert payload["snapshot_id"] == snapshot.snapshot_id
    assert payload["benchmark_signature"] == "sha256:benchmark:fixture-v2"
    assert payload["model_keys"] == ["model-a", "model-b"]
    assert payload["git_commits"] == ["fixture-commit"]
    assert set(payload["run_ids"]) == {"run-model-a", "run-model-b"}
    assert len(payload["sources"]["capability_payload_sha256"]) == 64
    assert payload["comparison"]["paired_count"] == 1
    assert payload["comparison"]["practical_delta"] == 0.05



def test_decision_overview_aggregates_known_api_cost(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_run(
        results,
        run_id="run-api",
        completed_at="2026-10-05T09:00:00+00:00",
        score=0.75,
        model_key="model-api",
        model_signature="sha256:model:model-api",
        deployment="api",
        estimated_cost_usd=0.002,
        latency_ms=240.0,
    )
    summary = project_results(results_root=results, rebuild=True)
    output = results / "analytics" / "dashboard"

    exported = export_dashboard_data(
        database_path=Path(summary.database_path),
        output_dir=output,
    )

    overview = json.loads(Path(exported["overview"]).read_text())
    model = overview["decision"]["model_summaries"][0]

    assert model["overall_quality_score"] == 75.0
    assert model["latency_p50_ms"] == 240.0
    assert model["latency_p95_ms"] == 240.0
    assert model["provider_cost_status"] == "complete"
    assert model["provider_cost_known"] is True
    assert model["provider_cost_priced_cases"] == 1
    assert model["provider_cost_total_cases"] == 1
    assert model["provider_cost_coverage_rate"] == 1.0
    assert model["provider_cost_observed_total_usd"] == 0.002
    assert model["provider_cost_total_usd"] == 0.002
    assert model["provider_cost_per_1k_cases_usd"] == 2.0
    assert model["provider_cost_pricing"]["as_of"] == "2026-09-20"
    assert model["provider_cost_pricing"]["source"] == "Fixture frozen pricing"
