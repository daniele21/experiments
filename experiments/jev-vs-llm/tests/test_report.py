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
                "input_state": "I need help with class a.",
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
                "input_state": "This request is outside scope.",
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
                "input_state": "I need help with class a but the model misses it.",
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
                "input_state": "Another outside-scope request.",
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
    assert "API cost by experiment" in text
    assert "Per-class breakdown" in text
    assert "Routing cases" in text
    assert "Calibration predictions" in text
    assert "case-search" in text
    assert "I need help with class a." in text
    assert "Error explorer" in text


def test_report_gap_analysis_and_leaderboard(tmp_path: Path):
    rows = pd.DataFrame(
        [
            {
                "run_group": "g_lead",
                "suite": "public-routing",
                "runner_location": "mac",
                "experiment": "01-routing-public",
                "case_id": "c1",
                "input_state": "Transfer money to friend",
                "provider": "local-korgis",
                "model": "model-fast",
                "question_id": "intent",
                "expected": "transfer",
                "actual": "transfer",
                "correct": True,
                "confidence": 0.9,
                "predicted_probability": 0.9,
                "latency_ms": 500.0,
                "input_tokens": 100,
                "output_tokens": 10,
                "estimated_cost_usd": 0.0,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "in_scope",
                "run_timestamp_utc": "2026-09-21T08:00:00Z",
            },
            {
                "run_group": "g_lead",
                "suite": "public-routing",
                "runner_location": "mac",
                "experiment": "01-routing-public",
                "case_id": "c1",
                "input_state": "Transfer money to friend",
                "provider": "local-korgis",
                "model": "model-slow",
                "question_id": "intent",
                "expected": "transfer",
                "actual": "other",
                "correct": False,
                "confidence": 0.5,
                "predicted_probability": 0.5,
                "latency_ms": 2000.0,
                "input_tokens": 100,
                "output_tokens": 10,
                "estimated_cost_usd": 0.0,
                "valid": True,
                "error": None,
                "primary_metric": True,
                "difficulty": "in_scope",
                "run_timestamp_utc": "2026-09-21T08:00:00Z",
            },
        ]
    )
    raw = tmp_path / "results_lead.csv"
    html = tmp_path / "report_lead.html"
    rows.to_csv(raw, index=False)

    build_report(raw, html, run_group="g_lead")

    text = html.read_text(encoding="utf-8")
    assert "Leaderboard" in text
    assert "model-fast" in text
    assert "model-slow" in text
    assert "Leader" in text
    assert "Speed Champion" in text or "Fastest" in text

