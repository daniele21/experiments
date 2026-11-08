from __future__ import annotations

from pathlib import Path

from imagegen_bench.planning import build_run_plan

ROOT = Path(__file__).parents[1]


def test_one_image_canary_covers_local_photorealism():
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-turbo-gguf-q4km"],
        profile_id="canary",
    )
    assert plan.profile_id == "canary"
    assert len(plan.prompts) == 1
    assert plan.prompts[0].category == "photorealism"
    assert plan.outputs_per_prompt == 1
    assert plan.seed == 42
    assert plan.models[0].generation["size"] == "1024x1024"
    assert plan.models[0].generation["num_inference_steps"] == 8


def test_bounded_mac_pilot_runner_owns_canary_and_telemetry():
    source = (ROOT / "scripts" / "run_mac_pilot.sh").read_text()
    assert 'canary) EXPECTED_IMAGES=1' in source
    assert 'pilot) EXPECTED_IMAGES=4' in source
    assert 'BENCHMARK_PROFILE' in source
    assert "mac_resource_samples.jsonl" in source
    assert "runtime_metrics.json" in source
    assert "admission-probe.json" in source
    assert "== expected" in source
    assert "runtime_metrics.json" in source
