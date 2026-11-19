from __future__ import annotations

from pathlib import Path

from imagegen_bench.planning import build_run_plan

ROOT = Path(__file__).parents[1]


def test_flux_klein_local_arm_resolves_through_korgis():
    plan = build_run_plan(ROOT, model_keys=["flux-3-image-klein-gguf-q5km"], profile_id="smoke")
    (flux,) = plan.models
    assert flux.provider_key == "korgis-image"
    assert flux.runtime_key == "korgis-image-local"
    assert flux.generation["size"] == "1024x1024"
    assert flux.benchmark_mapping["quantization"] == "Q5_K_M"
