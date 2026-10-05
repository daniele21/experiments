from pathlib import Path

import pandas as pd

from jev_bench.report import build_report
from jev_bench.reporting.data import select_run_group
from jev_bench.reporting.export import build_benchmark_payload


def _run_row(run_id, timestamp, **overrides):
    return {
        "run_id": run_id, "run_group": "shared-group", "run_timestamp_utc": timestamp,
        "suite": "public-routing", "experiment": "01-routing-public",
        "dataset": "banking77", "case_id": "case-1", "input_state": "Transfer money",
        "provider": "local-korgis", "model": "example", "thinking_mode": "off",
        "question_id": "intent", "expected": "transfer", "actual": "transfer",
        "correct": True, "valid": True, "primary_metric": True, "error": None,
        "confidence": 0.9, "predicted_probability": 0.9, "latency_ms": 100,
        "input_tokens": 10, "output_tokens": 2, "estimated_cost_usd": 0,
        **overrides,
    }


def test_latest_selection_keeps_failed_runs_and_separate_datasets_and_configurations():
    rows = pd.DataFrame([
        _run_row("old", "2026-09-21T10:00:00Z"),
        _run_row("failed", "2026-09-23T10:00:00Z", valid=False, correct=False),
        _run_row("thinking", "2026-09-22T10:00:00Z", thinking_mode="on"),
        _run_row("other-data", "2026-09-21T10:00:00Z", dataset="clinc150"),
        _run_row("other-provider", "2026-09-21T10:00:00Z", provider="another-provider"),
        _run_row("temperature", "2026-09-21T10:00:00Z", temperature=0.7),
    ])
    selected, _ = select_run_group(rows)
    assert set(selected.run_id) == {"failed", "thinking", "other-data", "other-provider", "temperature"}


def test_dashboard_uses_latest_public_runs_in_every_dataset_view(tmp_path, monkeypatch):
    monkeypatch.setattr("jev_bench.reporting.export._detect_hardware", dict)
    rows = pd.DataFrame([
        _run_row("old", "2026-09-21T10:00:00Z"),
        _run_row("latest", "2026-09-23T10:00:00Z", correct=False, actual="other"),
        _run_row("clinc", "2026-09-22T10:00:00Z", dataset="clinc150", case_id="oos-1"),
        _run_row("smoke", "2026-09-24T10:00:00Z", dataset="", suite="smoke-routing",
                 experiment="01-routing", model="smoke-only"),
    ])
    raw = tmp_path / "runs.csv"
    rows.to_csv(raw, index=False)
    payload = build_benchmark_payload(raw, run_group="shared-group")
    assert payload["metadata"]["total_rows"] == 2
    assert len(payload["models"]) == 1
    assert payload["leaderboard"][0]["accuracy"] == 0.5
    assert payload["leaderboard"][0]["run_ids"] == ["clinc", "latest"]
    assert set(payload["dataset_views"]) == {"banking77", "clinc150"}
    banking = payload["dataset_views"]["banking77"]
    assert banking["kpi_cards"]["leader"]["accuracy"] == 0
    assert banking["leaderboard"][0]["total_count"] == 1
    assert banking["routing"]["cases"][0]["actual"] == "other"
    assert payload["dataset_views"]["clinc150"]["leaderboard"][0]["accuracy"] == 1


def test_smoke_only_dashboard_has_empty_benchmark_state(tmp_path, monkeypatch):
    monkeypatch.setattr("jev_bench.reporting.export._detect_hardware", dict)
    raw = tmp_path / "smoke.csv"
    pd.DataFrame([_run_row("smoke", "2026-09-23T10:00:00Z", dataset="",
                           suite="smoke-routing", experiment="01-routing")]).to_csv(raw, index=False)
    payload = build_benchmark_payload(raw)
    assert payload["models"] == []
    assert payload["datasets"] == []
    assert payload["kpi_cards"]["total_requests"] == 0


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
    assert "window.__BENCHMARK_DATA__" in text
    assert "gpt-5.6-luna" in text
    assert "jev-test" in text
    assert "routing" in text
    assert "calibration" in text
    assert "I need help with class a." in text
    assert "local_parameters" in text


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
