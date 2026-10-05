from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from model_capability_bench.sharing.render import (
    build_share_cards,
    render_share_snapshot,
)


def _snapshot() -> dict:
    return {
        "schema_version": "1",
        "snapshot_id": "snapshot-fixture",
        "title": "Local vs API structured output",
        "capability_id": "structured-output",
        "model_keys": ["local", "api"],
        "benchmark_signature": "sha256:benchmark:fixture",
        "profile": "core",
        "run_ids": ["run-local", "run-api"],
        "git_commits": ["fixture-commit"],
        "methodology": {"paired_same_cases": True},
        "cells": [
            {
                "model_key": "local",
                "primary_metric": "exact_match",
                "primary_value": 0.82,
                "sample_count": 60,
                "failure_count": 0,
                "execution_signature": "sha256:execution:same",
                "resource_summary": {
                    "process_cpu_percent_avg": 140.0,
                    "process_rss_bytes_peak": 1_500_000_000,
                },
            },
            {
                "model_key": "api",
                "primary_metric": "exact_match",
                "primary_value": 0.90,
                "sample_count": 60,
                "failure_count": 0,
                "execution_signature": "sha256:execution:same",
                "resource_summary": {
                    "process_cpu_percent_avg": 3.0,
                    "process_rss_bytes_peak": 250_000_000,
                },
            },
        ],
        "comparison": {
            "delta_b_minus_a": 0.08,
            "ci95_low": 0.02,
            "ci95_high": 0.14,
            "paired_count": 60,
            "practical_delta": 0.05,
            "exceeds_practical_delta": True,
        },
        "family_breakdown": [
            {"model_key": "local", "family": "nested", "value": 0.75},
            {"model_key": "api", "family": "nested", "value": 0.92},
        ],
    }


def test_share_cards_are_fixed_size_snapshot_only_views():
    cards = build_share_cards(_snapshot())

    assert len(cards) == 5
    assert all("width: 1080px" in card for card in cards)
    assert all("height: 1350px" in card for card in cards)
    assert all("snapshot-fixture" in card for card in cards)
    assert "same-case paired comparison" in cards[1].lower()
    assert "Execution signatures match" in cards[3]
    assert "sha256:benchmark:fixture" in cards[4]


def test_share_cards_reject_unknown_schema():
    snapshot = _snapshot()
    snapshot["schema_version"] = "99"

    with pytest.raises(ValueError, match="unsupported share snapshot"):
        build_share_cards(snapshot)


def test_share_renderer_writes_five_pngs_and_pdf_with_browser_contract(
    tmp_path: Path,
):
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(__import__("json").dumps(_snapshot()))
    chrome = tmp_path / "chrome"
    chrome.write_text("fixture")

    def fake_runner(command, **_kwargs):
        for arg in command:
            if arg.startswith("--screenshot="):
                Path(arg.split("=", 1)[1]).write_bytes(b"PNG")
            if arg.startswith("--print-to-pdf="):
                Path(arg.split("=", 1)[1]).write_bytes(b"%PDF-fixture")
        return subprocess.CompletedProcess(command, 0, "", "")

    summary = render_share_snapshot(
        snapshot_path=snapshot_path,
        chrome_binary=str(chrome),
        runner=fake_runner,
    )

    assert len(summary.png_paths) == 5
    assert all(Path(path).is_file() for path in summary.png_paths)
    assert summary.pdf_path is not None
    assert Path(summary.pdf_path).read_bytes().startswith(b"%PDF")
