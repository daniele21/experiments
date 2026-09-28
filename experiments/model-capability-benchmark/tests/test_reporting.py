from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmark_core import append_jsonl_record

from model_capability_bench.reporting import (
    ReportDataError,
    ReportingConfig,
    load_benchmark_report,
    load_reporting_config,
    render_html_report,
    write_report,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest(run_dir: Path) -> None:
    payload = {
        "schema_version": "1",
        "run": {
            "run_id": "run-current",
            "run_group": "fixture-group",
        },
        "suite": {
            "suite_id": "capability-core",
            "version": "1",
            "profile": "smoke",
            "seed": 42,
        },
        "models": [
            {
                "model_key": "local-model",
                "model_id": "vendor/local",
                "effective_model_id": "local-runtime-id",
                "runtime_key": "korgis-local",
                "provider_key": "korgis",
                "deployment": "local",
                "lifecycle": "managed",
            },
            {
                "model_key": "api-model",
                "model_id": "provider/api",
                "effective_model_id": "provider/api",
                "runtime_key": "api-runtime",
                "provider_key": "api",
                "deployment": "api",
                "lifecycle": "external",
            },
        ],
        "capabilities": [
            {
                "capability_id": "reasoning",
                "task_id": "mathematical-reasoning",
                "dataset_ids": ["math-dataset"],
                "metrics": [
                    {
                        "name": "final_answer_accuracy",
                        "source": "task_metric",
                        "reducer": "mean",
                        "field": None,
                        "primary": True,
                    },
                    {
                        "name": "latency_p95_ms",
                        "source": "inference",
                        "reducer": "p95",
                        "field": "latency_ms",
                        "primary": False,
                    },
                    {
                        "name": "estimated_cost_usd",
                        "source": "inference",
                        "reducer": "sum",
                        "field": "estimated_cost_usd",
                        "primary": False,
                    },
                ],
            },
            {
                "capability_id": "missing-capability",
                "task_id": "structured-output",
                "dataset_ids": ["structured-dataset"],
                "metrics": [
                    {
                        "name": "schema_valid_rate",
                        "source": "task_metric",
                        "reducer": "mean",
                        "field": None,
                        "primary": True,
                    }
                ],
            },
        ],
        "config_checksums": {},
        "evidence": {
            "state": "state.jsonl",
            "raw": "raw.jsonl",
            "evaluation": "evaluation.jsonl",
            "aggregates": "aggregates.jsonl",
            "report_index": "report_index.jsonl",
            "events": "events.jsonl",
        },
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _raw(
    run_dir: Path,
    *,
    case_id: str,
    attempt: int,
    model_key: str,
    sample_id: str,
    prediction,
    latency_ms: float,
    cost,
) -> None:
    append_jsonl_record(
        {
            "case_id": case_id,
            "attempt": attempt,
            "record": {
                "run_id": "run-current",
                "run_group": "fixture-group",
                "suite_id": "capability-core",
                "task_id": "mathematical-reasoning",
                "sample_id": sample_id,
                "provider_id": "fixture",
                "model_id": model_key,
                "raw_output": {"answer": prediction, "attempt": attempt},
                "normalized_output": {"answer": prediction},
                "latency_ms": latency_ms,
                "input_tokens": 10,
                "output_tokens": 2,
                "estimated_cost_usd": cost,
                "valid": True,
                "error_kind": None,
                "error_message": None,
                "metadata": {
                    "model_key": model_key,
                    "capability_id": "reasoning",
                    "dataset_id": "math-dataset",
                    "sample_id": sample_id,
                },
            },
            "metadata": {
                "model_key": model_key,
                "capability_id": "reasoning",
                "dataset_id": "math-dataset",
                "sample_id": sample_id,
            },
        },
        run_dir / "raw.jsonl",
    )


def _evaluation(
    run_dir: Path,
    *,
    case_id: str,
    attempt: int,
    sample_id: str,
    expected: str,
    prediction: str,
) -> None:
    append_jsonl_record(
        {
            "case_id": case_id,
            "attempt": attempt,
            "record": {
                "run_id": "run-current",
                "task_id": "mathematical-reasoning",
                "sample_id": sample_id,
                "evaluator_version": "1",
                "expected": expected,
                "prediction": prediction,
                "metrics": [
                    {
                        "name": "final_answer_accuracy",
                        "value": float(expected == prediction),
                        "primary": True,
                        "metadata": {},
                    }
                ],
                "valid": True,
                "error": None,
                "metadata": {"dataset_id": "math-dataset"},
            },
        },
        run_dir / "evaluation.jsonl",
    )


def _aggregate(
    run_dir: Path,
    *,
    model_key: str,
    metric: str,
    value,
    sample_count: int = 1,
) -> None:
    append_jsonl_record(
        {
            "run_id": "run-current",
            "run_group": "fixture-group",
            "model_key": model_key,
            "capability_id": "reasoning",
            "task_id": "mathematical-reasoning",
            "dataset_ids": ["math-dataset"],
            "profile": "smoke",
            "metric": metric,
            "primary": metric == "final_answer_accuracy",
            "source": "task_metric",
            "reducer": "mean",
            "value": value,
            "sample_count": sample_count,
            "failure_count": 0,
        },
        run_dir / "aggregates.jsonl",
    )


def _fixture_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True)
    _manifest(run_dir)

    _raw(
        run_dir,
        case_id="case-local-1",
        attempt=1,
        model_key="local-model",
        sample_id="math-1",
        prediction="42",
        latency_ms=8.0,
        cost=0.0,
    )
    _evaluation(
        run_dir,
        case_id="case-local-1",
        attempt=1,
        sample_id="math-1",
        expected="42",
        prediction="42",
    )
    _raw(
        run_dir,
        case_id="case-local-2",
        attempt=1,
        model_key="local-model",
        sample_id="math-2",
        prediction="7",
        latency_ms=12.0,
        cost=0.0,
    )
    _evaluation(
        run_dir,
        case_id="case-local-2",
        attempt=1,
        sample_id="math-2",
        expected="8",
        prediction="7",
    )

    # A later attempt exists in evidence but is deliberately not selected by report_index.
    _raw(
        run_dir,
        case_id="case-local-1",
        attempt=2,
        model_key="local-model",
        sample_id="math-1",
        prediction="WRONG-LATER-ATTEMPT",
        latency_ms=99.0,
        cost=0.0,
    )
    _evaluation(
        run_dir,
        case_id="case-local-1",
        attempt=2,
        sample_id="math-1",
        expected="42",
        prediction="WRONG-LATER-ATTEMPT",
    )

    _raw(
        run_dir,
        case_id="case-api-1",
        attempt=1,
        model_key="api-model",
        sample_id="math-1",
        prediction="42",
        latency_ms=25.0,
        cost=None,
    )
    _evaluation(
        run_dir,
        case_id="case-api-1",
        attempt=1,
        sample_id="math-1",
        expected="42",
        prediction="42",
    )

    append_jsonl_record(
        {
            "run_id": "run-current",
            "run_group": "fixture-group",
            "model_key": "local-model",
            "capability_id": "reasoning",
            "task_id": "mathematical-reasoning",
            "profile": "smoke",
            "cases": [
                {"case_id": "case-local-1", "attempt": 1},
                {"case_id": "case-local-2", "attempt": 1},
            ],
            "dataset_ids": ["math-dataset"],
            "failure_count": 0,
        },
        run_dir / "report_index.jsonl",
    )
    append_jsonl_record(
        {
            "run_id": "run-current",
            "run_group": "fixture-group",
            "model_key": "api-model",
            "capability_id": "reasoning",
            "task_id": "mathematical-reasoning",
            "profile": "smoke",
            "cases": [{"case_id": "case-api-1", "attempt": 1}],
            "dataset_ids": ["math-dataset"],
            "failure_count": 0,
        },
        run_dir / "report_index.jsonl",
    )

    for model_key, accuracy, latency, cost, count in (
        ("local-model", 0.5, 12.0, 0.0, 2),
        ("api-model", 1.0, 25.0, None, 1),
    ):
        _aggregate(
            run_dir,
            model_key=model_key,
            metric="final_answer_accuracy",
            value=accuracy,
            sample_count=count,
        )
        _aggregate(
            run_dir,
            model_key=model_key,
            metric="latency_p95_ms",
            value=latency,
            sample_count=count,
        )
        _aggregate(
            run_dir,
            model_key=model_key,
            metric="estimated_cost_usd",
            value=cost,
            sample_count=count,
        )

    append_jsonl_record(
        {
            "event": "run_completed",
            "timestamp_utc": "2026-09-27T20:00:00+00:00",
            "metadata": {
                "run_id": "run-current",
                "completed_cases": 3,
            },
        },
        run_dir / "events.jsonl",
    )
    append_jsonl_record(
        {
            "event": "old_event",
            "metadata": {"run_id": "old-run"},
        },
        run_dir / "events.jsonl",
    )


def test_report_uses_exact_indexed_attempts_and_preserves_unknown_cost(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _fixture_run(run_dir)
    config = ReportingConfig(
        title="Capability report",
        html_filename="report.html",
        json_filename="report.json",
        numeric_precision=3,
        max_case_rows_per_cell=1,
    )

    report = load_benchmark_report(run_dir, config)

    assert [model.model_key for model in report.models] == [
        "local-model",
        "api-model",
    ]
    reasoning = report.capabilities[0]
    local, api = reasoning.cells

    assert local.primary_metric == "final_answer_accuracy"
    assert local.primary_value == 0.5
    assert local.metrics["estimated_cost_usd"] == 0.0
    assert api.metrics["estimated_cost_usd"] is None
    assert local.sample_count == 2
    assert local.truncated_case_count == 1
    assert local.cases[0].attempt == 1
    assert local.cases[0].prediction == "42"
    assert "WRONG-LATER-ATTEMPT" not in str(local.cases[0])
    assert len(report.events) == 1

    missing = report.capabilities[1]
    assert all(cell.primary_value is None for cell in missing.cells)
    assert all(cell.sample_count == 0 for cell in missing.cells)


def test_html_is_neutral_and_exported_with_machine_readable_report(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _fixture_run(run_dir)
    config = ReportingConfig(
        title="Capability report",
        html_filename="report.html",
        json_filename="report.json",
        numeric_precision=3,
        max_case_rows_per_cell=10,
    )
    report = load_benchmark_report(run_dir, config)

    rendered = render_html_report(report, config)
    lowered = rendered.lower()

    assert "primary capability matrix" in lowered
    assert "local-model" in rendered
    assert "api-model" in rendered
    assert "final_answer_accuracy" in rendered
    assert "unknown cost is null" in lowered
    for banned in ("winner", "leader", "fastest", "sweet spot"):
        assert banned not in lowered

    outputs = write_report(report, config, run_dir)
    assert outputs.html_path.is_file()
    assert outputs.json_path.is_file()
    payload = json.loads(outputs.json_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-current"
    assert payload["capabilities"][0]["cells"][1]["metrics"][
        "estimated_cost_usd"
    ] is None


def test_reporting_config_is_strict(tmp_path: Path) -> None:
    root = tmp_path / "config"
    root.mkdir()
    (root / "reporting.yaml").write_text(
        """
reporting:
  title: Fixture
  html_filename: report.html
  json_filename: report.json
  numeric_precision: 2
  max_case_rows_per_cell: 10
  typo: true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="typo"):
        load_reporting_config(root)


def test_report_rejects_missing_exact_indexed_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _fixture_run(run_dir)
    (run_dir / "evaluation.jsonl").unlink()
    config = ReportingConfig(
        title="Capability report",
        html_filename="report.html",
        json_filename="report.json",
        numeric_precision=2,
        max_case_rows_per_cell=10,
    )

    with pytest.raises(ReportDataError, match="missing evidence"):
        load_benchmark_report(run_dir, config)


def test_repository_reporting_config_loads() -> None:
    config = load_reporting_config(ROOT)

    assert config.title == "Model Capability Benchmark"
    assert config.max_case_rows_per_cell == 100
