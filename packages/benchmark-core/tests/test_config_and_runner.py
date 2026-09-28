from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core.config import (
    ConfigError,
    load_yaml_mapping,
    load_yaml_section,
    parse_csv_selection,
)
from benchmark_core.reporting import summarize_records
from benchmark_core.runner import BenchmarkArm, execute_arm


def test_yaml_mapping_and_section_loader(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
models:
  model-a:
    model_id: vendor/model-a
profile: smoke
""".strip(),
        encoding="utf-8",
    )

    payload = load_yaml_mapping(path)
    models = load_yaml_section(path, "models")

    assert payload["profile"] == "smoke"
    assert models == {"model-a": {"model_id": "vendor/model-a"}}


def test_yaml_loader_rejects_non_mapping_root(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="YAML mapping"):
        load_yaml_mapping(path)


def test_csv_selection_deduplicates_and_expands_all() -> None:
    assert parse_csv_selection("a,b,a") == ["a", "b"]
    assert parse_csv_selection("all", available=["a", "b"]) == ["a", "b"]

    with pytest.raises(ConfigError, match="At least one"):
        parse_csv_selection("")


def test_execute_arm_captures_success_and_failure() -> None:
    arm = BenchmarkArm(model_key="model-a", task_id="routing")

    success = execute_arm(arm, lambda: {"ok": True})
    failure = execute_arm(arm, lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert success.succeeded is True
    assert success.value == {"ok": True}
    assert success.elapsed_s >= 0

    assert failure.succeeded is False
    assert failure.error_type == "RuntimeError"
    assert failure.error_message == "boom"


def test_summary_is_dataframe_independent() -> None:
    summary = summarize_records(
        [
            {"valid": True, "correct": True, "latency_ms": 10.0},
            {"valid": True, "correct": False, "latency_ms": 30.0},
        ]
    )

    assert summary == {
        "total_cases": 2,
        "valid_cases": 2,
        "correct_cases": 1,
        "accuracy_pct": 50.0,
        "avg_latency_ms": 20.0,
    }
