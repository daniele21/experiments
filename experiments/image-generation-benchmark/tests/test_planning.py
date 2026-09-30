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


def test_qwen_local_plan_resolves_korgis_runtime() -> None:
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-local"],
        profile_id="smoke",
    )

    [model] = plan.models
    assert model.model_id == "qwen-image-2.1-mflux-q8"
    assert model.runtime_key == "korgis-image-local"
    assert model.provider_key == "korgis-image"
    assert model.provider_type == "korgis-image"
    assert model.base_url_env == "KORGIS_BASE_URL"
    assert model.api_key_env == "KORGIS_API_KEY"
    assert model.generation["size"] == "1024x1024"
    assert model.generation["num_inference_steps"] == 40
    assert model.benchmark_mapping["runtime"] == "mflux"
    assert model.benchmark_mapping["quantization"] == "Q8"



def test_qwen_gguf_local_plan_resolves_korgis_sdcpp_runtime() -> None:
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-local-gguf-q4km"],
        profile_id="smoke",
    )

    [model] = plan.models
    assert model.model_id == "qwen-image-2.1-gguf-q4km"
    assert model.runtime_key == "korgis-image-local"
    assert model.provider_key == "korgis-image"
    assert model.provider_type == "korgis-image"
    assert model.base_url_env == "KORGIS_BASE_URL"
    assert model.generation["size"] == "512x512"
    assert model.generation["num_inference_steps"] == 20
    assert model.generation["guidance_scale"] == 6.0
    assert model.generation["sampling_method"] == "euler"
    assert model.benchmark_mapping["runtime"] == "stable-diffusion.cpp"
    assert model.benchmark_mapping["quantization"] == "Q4_K_M"



def test_qwen_gguf_budget_keeps_quality_resolution() -> None:
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-local-gguf-q4km"],
        profile_id="budget",
    )

    [model] = plan.models
    assert model.generation["size"] == "1024x1024"
    assert model.generation["num_inference_steps"] == 20
