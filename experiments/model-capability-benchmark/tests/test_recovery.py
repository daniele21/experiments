from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from model_capability_bench.runner.recovery import select_error_cases


def _source(root: Path, rows: list[dict]) -> Path:
    root.mkdir()
    (root / "run_manifest.json").write_text(json.dumps({
        "suite": {"profile": "core", "seed": 42}, "run": {"run_id": root.name},
    }))
    (root / "state.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    return root


def _row(sample: str, status: str, valid: bool, time: str = "1") -> dict:
    return {"status": status, "timestamp_utc": time, "metadata": {
        "model_key": "model", "capability_id": "cap", "dataset_id": "dataset",
        "sample_id": sample, "valid": valid,
    }}


def test_latest_logical_attempt_controls_recovery_across_sources(tmp_path: Path) -> None:
    first = _source(tmp_path / "first", [
        _row("invalid", "completed", False),
        _row("failed", "failed", False),
        _row("fixed", "completed", False),
        _row("valid", "completed", True),
        _row("interrupted", "started", False),
    ])
    second = _source(tmp_path / "second", [_row("fixed", "completed", True, "2")])
    before = (first / "state.jsonl").read_bytes()
    selected, metadata = select_error_cases(
        [second, first], models=("model",), capabilities=("cap",), profile="core", seed=42,
    )
    assert {key[3] for key in selected} == {"invalid", "failed"}
    assert metadata["experiment_kind"] == "recovery"
    assert len(metadata["recovery_sources"]) == 2
    assert (first / "state.jsonl").read_bytes() == before


def test_recovery_rejects_different_profile_or_empty_selection(tmp_path: Path) -> None:
    source = _source(tmp_path / "source", [_row("valid", "completed", True)])
    with pytest.raises(ValueError, match="profile and seed"):
        select_error_cases([source], models=("model",), capabilities=("cap",), profile="smoke", seed=42)
    with pytest.raises(ValueError, match="No unsuccessful cases"):
        select_error_cases([source], models=("model",), capabilities=("cap",), profile="core", seed=42)


def test_cli_recovery_preview_and_source_protection(tmp_path: Path, monkeypatch, capsys) -> None:
    from model_capability_bench.cli import main

    row = _row("bad", "completed", False)
    row["metadata"]["model_key"] = "lfm2.5-24b-a2b-ud-q3-k-xl"
    row["metadata"]["capability_id"] = "structured-output"
    source = _source(tmp_path / "source", [row])
    output = tmp_path / "output"
    args = [
        "model-bench", "run", "--models", row["metadata"]["model_key"],
        "--capabilities", "structured-output", "--profile", "core",
        "--run-group", "recovery", "--run-id", "recovery", "--output-dir", str(output),
        "--max-output-tokens", "4096", "--rerun-errors-from", str(source), "--plan-only",
    ]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_case_count"] == 1
    assert payload["inference"]["max_output_tokens"] == 4096
    assert not output.exists()
    args[args.index(str(output))] = str(source)
    with pytest.raises(ValueError, match="must differ"):
        main()
