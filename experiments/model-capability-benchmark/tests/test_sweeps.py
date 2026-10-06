from __future__ import annotations

from pathlib import Path

from model_capability_bench.runner.sweeps import expand_sweep, load_sweep

ROOT = Path(__file__).resolve().parents[1]


def test_generation_sensitivity_is_ovat_and_deduplicates_baseline() -> None:
    spec = load_sweep(ROOT, "generation-sensitivity")
    points = expand_sweep(spec)

    assert spec.strategy == "one_at_a_time"
    assert len(points) == 14
    assert sum(point.is_baseline for point in points) == 1
    assert len({point.configuration_id for point in points}) == len(points)

    baseline = next(point for point in points if point.is_baseline)
    assert baseline.inference_config["temperature"] == 0.0
    assert baseline.inference_config["max_output_tokens"] == 256
    assert baseline.runtime_config["ctx_size"] == 4096

    ctx_16k = next(
        point
        for point in points
        if point.changed_dimension == "runtime.ctx_size"
        and point.runtime_config["ctx_size"] == 16384
    )
    assert ctx_16k.inference_config == baseline.inference_config


def test_factorial_sweep_expands_interactions() -> None:
    spec = load_sweep(ROOT, "focused-interactions")
    points = expand_sweep(spec)

    assert spec.strategy == "factorial"
    assert len(points) == 8
    assert sum(point.is_baseline for point in points) == 1
