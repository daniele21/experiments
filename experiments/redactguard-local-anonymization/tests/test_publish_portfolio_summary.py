"""Public benchmark exports may not turn synthetic coverage into model scores."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "redactguard_publisher", ROOT / "scripts" / "publish_portfolio_summary.py"
)
assert SPEC and SPEC.loader
PUBLISHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLISHER)


def test_catalog_from_versioned_source_is_dataset_only():
    result = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    assert result["publication"]["has_published_model_metrics"] is False
    assert result["models"] == []
    by_id = {entry["id"]: entry for entry in result["datasets"]}
    assert by_id["healthcare"]["cases"] == 48
    assert by_id["ambiguous"]["cases"] == 48
    assert by_id["challenge"]["cases"] == 46
    assert by_id["smoke"]["cases"] == 20
    assert by_id["document-e2e"]["cases"] == 5
    assert by_id["realistic"]["documents"] == 11
    assert by_id["realistic"]["gold_spans"] == 1566
    assert all(x["results_status"] == "no_published_run" for x in result["datasets"])
    assert "Mario Rossi" not in json.dumps(result)


def test_model_scores_require_review_and_complete_run(tmp_path):
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    with pytest.raises(ValueError, match="approval"):
        PUBLISHER.publish_run(catalog, tmp_path, approved=False)
    (tmp_path / "manifest.json").write_text(json.dumps({
        "evaluation_schema": "redactguard-evaluation-v3",
        "models": ["test-llm"], "dataset": "data/healthcare/cases.jsonl", "cases": 17,
    }), encoding="utf-8")
    (tmp_path / "metrics.json").write_text(json.dumps({
        "test-llm": {
            "evaluation_schema": "redactguard-evaluation-v3", "quality_available": True,
            "pii_recall": 0.9, "system_leakage_rate": 0.1,
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Partial"):
        PUBLISHER.publish_run(catalog, tmp_path, approved=True)


def test_fail_closed_for_contract_failure(tmp_path):
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "evaluation_schema": "redactguard-evaluation-v3",
        "models": ["test-llm"], "dataset": "data/healthcare/cases.jsonl", "cases": 48,
        "run_id": "test-run", "benchmark_commit": "source-commit",
    }), encoding="utf-8")
    (tmp_path / "metrics.json").write_text(json.dumps({
        "test-llm": {
            "evaluation_schema": "redactguard-evaluation-v3", "quality_available": False,
            "status": "contract_failed",
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="contract-failed"):
        PUBLISHER.publish_run(catalog, tmp_path, approved=True)


def _sample_run(directory, *, dataset="healthcare", run_id="run-001", models=None):
    directory.mkdir(parents=True, exist_ok=True)
    models = models or ["qwen-2b", "nemotron-4b"]
    source = f"data/{dataset}/cases.jsonl"
    manifest = {
        "evaluation_schema": "redactguard-evaluation-v3",
        "run_id": run_id,
        "benchmark_commit": "source-commit",
        "backend": "korgis",
        "created_at": "2026-10-15T10:00:00Z",
        "host": {"system": "Darwin", "machine": "arm64"},
        "redactguard_contract": {"snapshot_sha256": "abcdefabcdefabcdef"},
        "models": models,
        "dataset": source,
        "cases": 48,
        "private_prompt": "DO NOT PUBLISH THIS",
    }
    metrics = {
        model: {
            "evaluation_schema": "redactguard-evaluation-v3",
            "status": "ok",
            "quality_available": True,
            "cases": 48,
            "evaluated_cases": 46,
            "inference_failures": 2,
            "inference_success_rate": 46 / 48,
            "pii_recall": 0.80 + index * 0.05,
            "system_pii_recall": 0.75 + index * 0.05,
            "precision": 0.90,
            "system_leakage_rate": 0.25 - index * 0.05,
            "latency_p95_ms": 720.0 + index * 120.0,
            "private_document": "PRIVATE DOCUMENT CONTENT",
        }
        for index, model in enumerate(models)
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (directory / "metrics.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )
    return directory


def test_publish_two_datasets_keeps_aggregate_provenance(tmp_path):
    first = _sample_run(tmp_path / "healthcare", run_id="hc-run")
    second = _sample_run(
        tmp_path / "ambiguous", dataset="ambiguous", run_id="amb-run"
    )
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    result = PUBLISHER.publish_runs(catalog, [first, second], approved=True)
    assert result["publication"]["has_published_model_metrics"] is True
    assert result["publication"]["run_count"] == 2
    assert len(result["models"]) == 4
    assert {row["dataset"] for row in result["models"]} == {
        "healthcare", "ambiguous"
    }
    hc = [row for row in result["models"] if row["dataset"] == "healthcare"]
    assert len({row["provenance"]["cohort_id"] for row in hc}) == 1
    assert {row["provenance"]["comparison_scope"] for row in hc} == {
        "same_run_exploratory"
    }
    assert hc[0]["cases"] == 48
    assert hc[0]["evaluated_cases"] == 46
    assert hc[0]["latency_p95_ms"] is not None
    output = json.dumps(result)
    assert "DO NOT PUBLISH THIS" not in output
    assert "PRIVATE DOCUMENT CONTENT" not in output


def test_cross_suite_duplicate_model_is_rejected(tmp_path):
    first = _sample_run(tmp_path / "first", run_id="one")
    second = _sample_run(tmp_path / "second", run_id="two")
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    with pytest.raises(ValueError, match="Duplicate model/dataset"):
        PUBLISHER.publish_runs(catalog, [first, second], approved=True)


def test_publisher_rejects_stale_source_commit(tmp_path):
    run = _sample_run(tmp_path / "run")
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="different-source")
    with pytest.raises(ValueError, match="benchmark_commit"):
        PUBLISHER.publish_runs(catalog, [run], approved=True)


def test_publisher_rejects_incomplete_model_rows(tmp_path):
    run = _sample_run(tmp_path / "run")
    metrics_file = run / "metrics.json"
    metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
    metrics["qwen-2b"]["evaluated_cases"] = 47
    metrics_file.write_text(json.dumps(metrics), encoding="utf-8")
    catalog = PUBLISHER.build_catalog(ROOT, source_ref="source-commit")
    with pytest.raises(ValueError, match="completeness"):
        PUBLISHER.publish_runs(catalog, [run], approved=True)
