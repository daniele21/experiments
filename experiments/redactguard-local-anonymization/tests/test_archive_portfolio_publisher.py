"""Regression tests for reviewed results.zip -> aggregate-only public evidence."""
from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "archive_publisher", ROOT / "scripts" / "publish_archived_results.py"
)
assert spec and spec.loader
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def _catalog() -> dict:
    return {
        "schema_version": 1,
        "benchmark": "redactguard-local-anonymization",
        "source": {"repository": "daniele21/experiments", "ref": "base-revision"},
        "publication": {
            "status": "dataset_evidence_only",
            "has_published_model_metrics": False,
            "contains_raw_pii": False,
        },
        "datasets": [{
            "id": "healthcare", "cases": 48, "title": "Healthcare",
            "results_status": "no_published_run",
        }],
        "models": [],
        "limitations": [],
    }


def _archive(tmp_path: Path, *, kind: str = "quality", count: int = 48) -> Path:
    run = "20261013T081117Z-suite-39803d12"
    base = f"results/suites/{run}/quality"
    manifest = {
        "kind": kind,
        "evaluation_schema": "redactguard-evaluation-v3",
        "dataset": "/Users/example/experiments/data/healthcare/cases.jsonl",
        "cases": count, "models": ["qwen3.5-4b-q4km", "qwen3.5-9b-q4km"],
        "run_id": run + "-quality",
        "benchmark_commit": "a" * 40,
        "redactguard_contract": {"snapshot_sha256": "b" * 64},
        "private_user_prompt": "NEVER EXPORT",
        "created_at": "2026-10-13T08:00:00Z",
    }
    metrics = {}
    for model in manifest["models"]:
        metrics[model] = {
            "evaluation_schema": "redactguard-evaluation-v3",
            "status": "ok", "quality_available": True,
            "cases": count, "evaluated_cases": count,
            "inference_failures": 0,
            "pii_recall": 0.9, "system_pii_recall": 0.9,
            "system_leakage_rate": 0.05, "precision": 0.8,
            "inference_success_rate": 1.0,
            "latency_p95_ms": 1500.0,
            "original_text": "PRIVATE PATIENT RECORD",
        }
    path = tmp_path / "results.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(base + "/manifest.json", json.dumps(manifest))
        archive.writestr(base + "/metrics.json", json.dumps(metrics))
    return path


def test_aggregate_only_and_provenance(tmp_path):
    archive = _archive(tmp_path)
    result = publisher.build_archive_summary(
        archive, _catalog(), ["20261013T081117Z-suite-39803d12"]
    )
    assert len(result["models"]) == 2
    assert result["publication"]["run_count"] == 1
    assert result["publication"]["has_published_model_metrics"] is True
    assert result["datasets"][0]["results_status"] == "published"
    assert result["models"][0]["provenance"]["comparison_scope"] == (
        "same_run_exploratory"
    )
    assert "observed_quality_run_p95" in result["models"][0]["latency_provenance"]
    exported = json.dumps(result)
    assert "PRIVATE PATIENT RECORD" not in exported
    assert "NEVER EXPORT" not in exported
    assert "/Users/example" not in exported


def test_fail_closed_for_partial_or_latency_runs(tmp_path):
    for kind, count in [("quality", 47), ("latency", 48)]:
        archive = _archive(tmp_path, kind=kind, count=count)
        with pytest.raises(ValueError):
            publisher.build_archive_summary(
                archive, _catalog(), ["20261013T081117Z-suite-39803d12"]
            )


def test_reject_duplicate_and_unapproved_names(tmp_path):
    archive = _archive(tmp_path)
    run = "20261013T081117Z-suite-39803d12"
    with pytest.raises(ValueError, match="unique"):
        publisher.build_archive_summary(archive, _catalog(), [run, run])
    with pytest.raises(ValueError, match="Unsafe"):
        publisher.build_archive_summary(
            archive, _catalog(), ["../../../private"]
        )


def test_reject_already_populated_catalog(tmp_path):
    archive = _archive(tmp_path)
    current = _catalog()
    current["models"] = [{"model": "existing"}]
    with pytest.raises(ValueError, match="dataset-only"):
        publisher.build_archive_summary(
            archive, current, ["20261013T081117Z-suite-39803d12"]
        )
