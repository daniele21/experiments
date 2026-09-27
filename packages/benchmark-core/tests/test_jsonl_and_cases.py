from __future__ import annotations

from pathlib import Path

from benchmark_core import (
    BenchmarkCaseIdentity,
    GenerationConfig,
    append_jsonl_record,
    read_jsonl_records,
)


def test_jsonl_store_appends_nested_records(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    append_jsonl_record(
        {"case_id": "a", "payload": {"values": (1, 2)}},
        path,
    )
    append_jsonl_record({"case_id": "b", "ok": True}, path)

    assert read_jsonl_records(path) == [
        {"case_id": "a", "payload": {"values": [1, 2]}},
        {"case_id": "b", "ok": True},
    ]


def test_case_identity_changes_with_semantic_run_inputs() -> None:
    base = BenchmarkCaseIdentity(
        suite_id="suite",
        suite_version="1",
        model_key="model",
        model_id="vendor/model",
        runtime_key="runtime",
        capability_id="classification",
        task_id="task",
        task_version="1",
        prompt_id="prompt",
        prompt_version="1",
        dataset_id="dataset",
        dataset_revision="rev-1",
        dataset_split="test",
        selection_fingerprint="sha256:selection",
        sample_id="sample-1",
        profile="smoke",
        generation=GenerationConfig(temperature=0.0, seed=42),
    )
    same = BenchmarkCaseIdentity(**base.__dict__)
    changed = BenchmarkCaseIdentity(
        **{
            **base.__dict__,
            "prompt_version": "2",
        }
    )

    assert base.case_id == same.case_id
    assert base.case_id.startswith("sha256:")
    assert base.case_id != changed.case_id
