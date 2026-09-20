from pathlib import Path

import pandas as pd

from jev_bench.report import build_report


def test_report_builds_interactive_html(tmp_path: Path):
    rows = pd.DataFrame(
        [
            {
                "run_group": "g1",
                "suite": "public-quick",
                "runner_location": "test",
                "experiment": "01-routing-public",
                "case_id": "r1",
                "provider": "jev",
                "model": "jev-test",
                "question_id": "intent",
                "expected": "a",
                "actual": "a",
                "correct": True,
                "confidence": 0.8,
                "predicted_probability": 0.9,
                "latency_ms": 100.0,
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "output_tokens": 2,
                "estimated_cost_usd": 0.00000042,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "in_scope",
            },
            {
                "run_group": "g1",
                "suite": "public-quick",
                "runner_location": "test",
                "experiment": "02-calibration-public",
                "case_id": "c1",
                "provider": "jev",
                "model": "jev-test",
                "question_id": "intent",
                "expected": "other",
                "actual": "other",
                "correct": True,
                "confidence": 0.7,
                "predicted_probability": 0.85,
                "latency_ms": 110.0,
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "output_tokens": 2,
                "estimated_cost_usd": 0.00000042,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "out_of_scope",
            },
            {
                "run_group": "g1",
                "suite": "public-quick",
                "runner_location": "test",
                "experiment": "01-routing-public",
                "case_id": "r2",
                "provider": "llm-workflow",
                "model": "gpt-5.6-luna",
                "question_id": "intent",
                "expected": "a",
                "actual": "b",
                "correct": False,
                "confidence": 0.6,
                "predicted_probability": 0.65,
                "latency_ms": 500.0,
                "input_tokens": 15,
                "cached_input_tokens": 0,
                "output_tokens": 4,
                "estimated_cost_usd": 0.0000078,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "in_scope",
            },
            {
                "run_group": "g1",
                "suite": "public-quick",
                "runner_location": "test",
                "experiment": "02-calibration-public",
                "case_id": "c2",
                "provider": "llm-workflow",
                "model": "gpt-5.6-luna",
                "question_id": "intent",
                "expected": "other",
                "actual": "a",
                "correct": False,
                "confidence": 0.9,
                "predicted_probability": 0.8,
                "latency_ms": 520.0,
                "input_tokens": 15,
                "cached_input_tokens": 0,
                "output_tokens": 4,
                "estimated_cost_usd": 0.0000078,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "out_of_scope",
            },
        ]
    )
    raw = tmp_path / "results.csv"
    html = tmp_path / "report.html"
    rows.to_csv(raw, index=False)

    build_report(raw, html, run_group="g1")

    text = html.read_text(encoding="utf-8")
    assert "Accuracy vs latency" in text
    assert "Probability calibration" in text
    assert "Most frequent confusion pairs" in text
    assert "Routing API cost" in text
    assert "Run details" in text
    assert "gpt-5.6-luna" in text
    assert "model-chip" in text
