from __future__ import annotations

from pathlib import Path

import pytest

from model_capability_bench import load_capability_suite
from model_capability_bench.runner.planning import plan_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_core_plan_is_vertical_and_bounded() -> None:
    bundle = load_capability_suite(ROOT)
    plan = plan_benchmark(bundle, profile_id="core")

    by_id = {
        item["capability_id"]: item
        for item in plan["capabilities"]
    }
    assert by_id["intent-classification"]["planned_cases"] == 154
    assert by_id["oos-calibration"]["planned_cases"] == 154
    assert by_id["structured-output"]["planned_cases"] == 60
    assert by_id["qa-abstention"]["planned_cases"] == 60
    assert by_id["mathematical-reasoning"]["planned_cases"] == 40
    assert plan["planned_cases_per_model"] == 468
    assert plan["configured_budget_per_model"]["target_local_seconds"] == 1680
    assert plan["configured_budget_per_model"]["hard_local_seconds"] == 2700
    assert plan["configured_budget_per_model"]["target_api_cost_usd"] == pytest.approx(0.45)
    assert plan["configured_budget_per_model"]["hard_api_cost_usd"] == 1.0
    assert by_id["structured-output"]["selection_strategy"] == "stratified"
    assert by_id["mathematical-reasoning"]["practical_delta"] == 0.05


def test_smoke_plan_keeps_all_vertical_families() -> None:
    bundle = load_capability_suite(ROOT)
    plan = plan_benchmark(
        bundle,
        profile_id="smoke",
        capability_ids=("structured-output", "qa-abstention"),
    )

    assert plan["planned_cases_per_model"] == 24
    assert all(
        item["selection_strategy"] == "stratified"
        for item in plan["capabilities"]
    )
