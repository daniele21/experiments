from __future__ import annotations

from pathlib import Path

from imagegen_bench.planning import build_run_plan

ROOT = Path(__file__).parents[1]


def test_pilot_covers_four_capabilities_with_one_sample_each():
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-turbo-gguf-q4km"],
        profile_id="pilot",
    )
    assert len(plan.prompts) == 4
    assert plan.outputs_per_prompt == 1
    assert plan.seed == 42
    assert {p.category for p in plan.prompts} == {
        "text_rendering", "compositional", "photorealism", "design",
    }
    assert plan.models[0].generation["size"] == "1024x1024"
    assert plan.models[0].generation["num_inference_steps"] == 8
