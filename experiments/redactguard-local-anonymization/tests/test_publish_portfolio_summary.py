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
    }), encoding="utf-8")
    (tmp_path / "metrics.json").write_text(json.dumps({
        "test-llm": {
            "evaluation_schema": "redactguard-evaluation-v3", "quality_available": False,
            "status": "contract_failed",
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="contract-failed"):
        PUBLISHER.publish_run(catalog, tmp_path, approved=True)
