from __future__ import annotations

from pathlib import Path

from imagegen_bench.planning import build_run_plan

ROOT = Path(__file__).parents[1]


def test_turbo_local_arm_is_distinct_from_standard_qwen_and_quality_sized():
    plan = build_run_plan(
        ROOT,
        model_keys=[
            "qwen-image-2.1-turbo-gguf-q4km",
            "qwen-image-2.1-local-gguf-q4km",
        ],
        profile_id="smoke",
    )
    turbo, standard = plan.models
    assert turbo.model_id == "qwen-image-2.1-turbo-gguf-q4km"
    assert turbo.provider_key == "korgis-image"
    assert turbo.runtime_key == "korgis-image-local"
    assert turbo.generation == {
        "output_format": "png",
        "size": "1024x1024",
        "num_inference_steps": 8,
        "guidance_scale": 1.0,
        "sampling_method": "euler",
    }
    assert turbo.benchmark_mapping["sigma_preset"] == "qwen-image-2.1-turbo-v1"
    assert standard.generation["size"] == "512x512"
    assert standard.model_id != turbo.model_id
