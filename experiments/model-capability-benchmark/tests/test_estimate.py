from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import InferenceResult, ResolvedModel, TokenUsage

from model_capability_bench import load_capability_suite
from model_capability_bench.runner.estimate import estimate_benchmark

ROOT = Path(__file__).resolve().parents[1]


class _Provider:
    provider_id = "fake"

    def __init__(self, model_id: str, cost: float | None) -> None:
        self.model_id = model_id
        self.cost = cost

    def generate(self, request):
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_output={},
            normalized_output={},
            latency_ms=100.0,
            usage=TokenUsage(input_tokens=20, output_tokens=5),
            estimated_cost_usd=self.cost,
        )


class _Runtime:
    def __init__(self, cost: float | None) -> None:
        self.cost = cost
        self.released: list[str] = []

    def prepare(self, model: ResolvedModel):
        return _Provider(model.effective_model_id, self.cost)

    def release(self, model: ResolvedModel) -> None:
        self.released.append(model.model.model_key)


def test_estimate_projects_same_vertical_subset_without_full_run(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    runtime = _Runtime(cost=0.001)

    result = estimate_benchmark(
        bundle,
        runtime_resolver=lambda model: runtime,
        cache_dir=tmp_path,
        environ={
            "KORGIS_BASE_URL": "http://fake.local/v1",
            "OPENAI_API_KEY": "fake",
        },
        profile_id="smoke",
        model_keys=("qwen3.5-2b-q4km",),
        capability_ids=("structured-output", "mathematical-reasoning"),
        pilot_cases=2,
        seed=42,
    )

    model = result["models"][0]
    by_id = {
        item["capability_id"]: item
        for item in model["capabilities"]
    }
    assert by_id["structured-output"]["planned_cases"] == 12
    assert by_id["mathematical-reasoning"]["planned_cases"] == 12
    assert by_id["structured-output"]["pilot_cases_observed"] == 2
    assert by_id["structured-output"]["projected_seconds_mean"] == pytest.approx(1.2)
    assert by_id["structured-output"]["projected_cost_usd"] == pytest.approx(0.012)
    assert model["projected_total_seconds_p95"] is not None
    assert model["within_hard_budget"] is True
    assert runtime.released == ["qwen3.5-2b-q4km"]


def test_estimate_uses_versioned_pricing_snapshot_when_provider_cost_missing(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    runtime = _Runtime(cost=None)

    result = estimate_benchmark(
        bundle,
        runtime_resolver=lambda model: runtime,
        cache_dir=tmp_path,
        environ={"OPENAI_API_KEY": "fake"},
        profile_id="smoke",
        model_keys=("gpt-5.6-luna",),
        capability_ids=("structured-output",),
        pilot_cases=1,
    )

    model = result["models"][0]
    capability = model["capabilities"][0]
    assert capability["cost_source"] == "pricing_snapshot"
    assert capability["projected_cost_usd"] == pytest.approx(0.00012)
    assert model["projected_total_cost_usd"] == pytest.approx(0.00012)
    assert model["within_hard_budget"] is True


def test_estimate_keeps_unknown_api_cost_unknown_without_snapshot_entry(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    runtime = _Runtime(cost=None)

    result = estimate_benchmark(
        bundle,
        runtime_resolver=lambda model: runtime,
        cache_dir=tmp_path,
        environ={"MINICPM_API_KEY": "fake"},
        profile_id="smoke",
        model_keys=("minicpm-v-4.6-1b",),
        capability_ids=("structured-output",),
        pilot_cases=1,
    )

    model = result["models"][0]
    assert model["projected_total_cost_usd"] is None
    assert model["within_hard_budget"] is None
