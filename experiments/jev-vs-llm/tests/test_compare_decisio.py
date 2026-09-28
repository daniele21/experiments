"""Checks for the standalone Decisio runner, without loading model weights."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/compare_decisio.py"
spec = importlib.util.spec_from_file_location("compare_decisio", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_invalid_predictions_remain_in_accuracy_and_f1():
    rows = [
        {
            "expected": "a",
            "choice": "a",
            "correct": True,
            "valid": True,
            "latency_ms": 10,
            "result": {},
            "runtime": {},
            "case_id": "1",
        },
        {
            "expected": "b",
            "choice": None,
            "correct": False,
            "valid": False,
            "latency_ms": 30,
            "result": {},
            "runtime": {},
            "case_id": "2",
        },
    ]
    summary = runner.summarize(rows)
    assert summary["accuracy"] == 0.5
    assert summary["macro_f1"] == 0.5
    assert summary["valid_rate"] == 0.5
    assert len(summary["errors"]) == 1
    assert summary["latency_p50_ms"] == 20
    assert summary["latency_p95_ms"] == 29


def test_direct_banking77_rejected_before_import_or_model_load(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--decisio-root",
            str(tmp_path),
            "--model",
            str(tmp_path / "missing.gguf"),
            "--dataset",
            "banking77",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "26 candidates" in result.stderr
    assert not output.exists()


def test_resume_rows_reject_duplicates(tmp_path):
    rows = tmp_path / "rows.jsonl"
    row = {"method": "semantic", "case_id": "case-1"}
    rows.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")

    try:
        runner.load_resume_rows(rows, methods=["semantic"], case_ids={"case-1"})
    except ValueError as exc:
        assert "duplicate saved result" in str(exc)
    else:
        raise AssertionError("duplicate rows must be rejected")


def test_resume_rows_accept_partial_run(tmp_path):
    rows = tmp_path / "rows.jsonl"
    expected = {"method": "semantic", "case_id": "case-1", "correct": True}
    rows.write_text(json.dumps(expected) + "\n")

    assert runner.load_resume_rows(
        rows, methods=["semantic", "json"], case_ids={"case-1", "case-2"}
    ) == [expected]
