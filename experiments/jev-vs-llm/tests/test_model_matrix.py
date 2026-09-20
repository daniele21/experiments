from jev_bench.cli import (
    DEFAULT_OPENAI_MODELS,
    _local_model_matrix,
    _model_matrix,
)
from jev_bench.providers.openai import OpenAIProvider


def test_default_model_matrix_contains_three_gpt_tiers(monkeypatch):
    monkeypatch.delenv("OPENAI_MODELS", raising=False)
    assert _model_matrix() == DEFAULT_OPENAI_MODELS
    assert DEFAULT_OPENAI_MODELS == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
    ]


def test_model_matrix_deduplicates_preserving_order():
    assert _model_matrix("gpt-5.6-sol,gpt-5.6-luna,gpt-5.6-sol") == [
        "gpt-5.6-sol",
        "gpt-5.6-luna",
    ]


def test_local_matrix_can_be_overridden():
    assert _local_model_matrix("qwen3.5-4b-q4km,nemotron-nano-4b") == [
        "qwen3.5-4b-q4km",
        "nemotron-nano-4b",
    ]


def test_gpt_decision_provider_defaults_to_no_reasoning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)

    provider = OpenAIProvider("gpt-5.6-luna")

    assert provider.reasoning_effort == "none"
