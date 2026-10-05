from __future__ import annotations

from pathlib import Path

from benchmark_core import load_registry, preflight_models

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models.yaml"


def test_committed_registry_resolves_local_and_api_models() -> None:
    registry = load_registry(REGISTRY)

    local = registry.resolve("qwen3.5-2b-q4km")
    api = registry.resolve("gpt-5.6-luna")

    assert local.runtime.deployment == "local"
    assert local.runtime.lifecycle == "managed"
    assert local.provider.provider_key == "korgis"
    assert local.effective_model_id == "qwen3.5-2b-q4km"
    assert local.model.artifact is not None
    assert local.model.artifact.quantization == "Q4_K_M"

    assert api.runtime.deployment == "api"
    assert api.provider.provider_key == "openai"
    assert api.effective_model_id == "gpt-5.6-luna"

    spark = registry.resolve("spark-x2.5-4b-q4km")
    assert spark.runtime.deployment == "local"
    assert spark.provider.provider_key == "korgis"
    assert spark.effective_model_id == "spark-x2.5-4b-q4km"
    assert spark.model.parameters_b == 4
    assert spark.model.artifact is not None
    assert spark.model.artifact.format == "gguf"
    assert spark.model.artifact.quantization == "Q4_K_M"
    assert spark.model.artifact.size_bytes == 2_600_224_352
    assert spark.model.artifact.metadata["sha256"] == (
        "adfcfa19a4ed6a5985da8bf565fe15f8e1a7e131d79bae2d19d48d1c40109428"
    )
    assert spark.model.artifact.metadata["required_runtime"] == "llama.cpp>=b10828"

    bonsai = registry.resolve("ternary-bonsai2-27b-ptq1")
    assert bonsai.runtime.deployment == "local"
    assert bonsai.provider.provider_key == "korgis"
    assert bonsai.effective_model_id == "ternary-bonsai2-27b-ptq1"
    assert bonsai.model.parameters_b == 27
    assert bonsai.model.artifact is not None
    assert bonsai.model.artifact.format == "gguf"
    assert bonsai.model.artifact.quantization == "PTQ1_0"
    assert bonsai.model.artifact.size_bytes == 5_946_648_928
    assert bonsai.model.artifact.metadata["required_runtime"] == "prismml-llama.cpp"


def test_committed_registry_preflight_is_selection_scoped() -> None:
    registry = load_registry(REGISTRY)

    local = registry.select(model_keys=["qwen3.5-2b-q4km"])
    local_preflight = preflight_models(
        registry,
        local,
        {"KORGIS_BASE_URL": "http://127.0.0.1:1235/v1"},
    )
    assert local_preflight.ok

    api = registry.select(model_keys=["gpt-5.6-luna"])
    api_preflight = preflight_models(registry, api, {})
    assert api_preflight.ok is False
    assert [issue.env_var for issue in api_preflight.issues] == ["OPENAI_API_KEY"]


def test_committed_registry_contains_no_machine_specific_paths_or_secrets() -> None:
    text = REGISTRY.read_text(encoding="utf-8")

    assert "/Users/" not in text
    assert "\\\\" not in text
    assert "api_key:" not in text
    assert "password:" not in text
    assert "secret:" not in text
