from __future__ import annotations

import json
from pathlib import Path

import pytest

from model_capability_bench.analytics.public_bundle import public_value, write_public_bundle


def _export(root: Path) -> None:
    root.mkdir()
    index = {"overview": "overview.json", "capabilities": {"cap": "cap.json"},
             "models": {"model": "model.json"}, "runs": {"run": "run.json"}}
    (root / "index.json").write_text(json.dumps(index))
    for name in ("overview", "cap", "model", "run"):
        (root / f"{name}.json").write_text(json.dumps({"name": name, "failure_rate": 0.03}))
    (root / "stale.json").write_text(json.dumps({"stale": True}))


def test_public_bundle_contains_all_views_and_replaces_previous_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "export"
    _export(root)
    destination = tmp_path / "published" / "dashboard-data.json"
    write_public_bundle(root, destination=destination)
    data = json.loads(destination.read_text())
    assert data["schema_version"] == "1"
    assert data["overview"]["name"] == "overview"
    assert data["capabilities"]["cap"]["name"] == "cap"
    assert data["models"]["model"]["name"] == "model"
    assert data["runs"]["run"]["name"] == "run"
    assert "stale" not in destination.read_text()
    (root / "overview.json").write_text(json.dumps({"failure_rate": 0.01}))
    write_public_bundle(root, destination=destination)
    assert json.loads(destination.read_text())["overview"]["failure_rate"] == 0.01
    assert not list(destination.parent.glob(".dashboard-data.json.*"))


def test_failed_export_keeps_public_snapshot_intact(tmp_path: Path) -> None:
    root = tmp_path / "export"
    _export(root)
    destination = tmp_path / "dashboard-data.json"
    write_public_bundle(root, destination=destination)
    before = destination.read_bytes()
    (root / "cap.json").write_text("invalid JSON")
    with pytest.raises(json.JSONDecodeError):
        write_public_bundle(root, destination=destination)
    assert destination.read_bytes() == before


def test_public_redaction_handles_serialized_metadata_and_keeps_metrics() -> None:
    data = public_value({
        "source_dir": "/Users/private/runs", "failure_rate": 0.03, "output_tokens": 4096,
        "execution_environment": {"cpu_model": "Apple M3 Pro", "total_memory_bytes": 100},
        "metadata_json": json.dumps({"model_path": "/Users/private/model.gguf", "api_key": "secret-value", "ctx_size": 8192}),
        "error_message": "failure at /private/tmp/model.log", "url": "https://user:password@example.com",
    })
    encoded = json.dumps(data)
    assert "/Users/" not in encoded and "/private/" not in encoded
    assert "secret-value" not in encoded and "user:password" not in encoded
    assert data["failure_rate"] == 0.03 and data["output_tokens"] == 4096
    assert data["execution_environment"]["cpu_model"] == "Apple M3 Pro"
    assert json.loads(data["metadata_json"])["ctx_size"] == 8192


def test_bundle_rejects_index_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "export"
    _export(root)
    index = json.loads((root / "index.json").read_text())
    index["overview"] = "../outside.json"
    (root / "index.json").write_text(json.dumps(index))
    with pytest.raises(ValueError, match="outside"):
        write_public_bundle(root, destination=tmp_path / "public.json")
