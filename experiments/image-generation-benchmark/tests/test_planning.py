from __future__ import annotations

from pathlib import Path

from imagegen_bench.planning import build_run_plan


ROOT = Path(__file__).parents[1]


def test_smoke_plan_is_deterministic_and_config_driven() -> None:
    first = build_run_plan(
        ROOT,
        model_keys=["openai-sunburst", "gemini-pro-image"],
        profile_id="smoke",
    )
    second = build_run_plan(
        ROOT,
        model_keys=["openai-sunburst", "gemini-pro-image"],
        profile_id="smoke",
    )

    assert first == second
    assert len(first.models) == 2
    assert len(first.prompts) == 4
    assert {prompt.category for prompt in first.prompts} == {
        "text_rendering",
        "compositional",
    }
    assert first.models[0].runtime_key == "openai-image-api"
    assert first.models[1].runtime_key == "gemini-image-api"
    assert first.models[0].benchmark_mapping["resolution"] == "1K"
    assert first.models[1].benchmark_mapping["resolution"] == "1K"
