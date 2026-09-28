from __future__ import annotations

from dataclasses import asdict

import pytest

from benchmark_core import (
    ArtifactSpec,
    GenerationConfig,
    InferenceError,
    InferenceProvider,
    InferenceRequest,
    InferenceResult,
    ModelSpec,
    ProviderSpec,
    RunContext,
    RunManifest,
    RuntimeSpec,
    TokenUsage,
)


class _EchoProvider:
    provider_id = "echo"

    def generate(self, request: InferenceRequest) -> InferenceResult:
        return InferenceResult(
            provider_id=self.provider_id,
            model_id="echo-model",
            raw_output=request.input,
            normalized_output=request.input,
            latency_ms=1.5,
            usage=TokenUsage(input_tokens=3, output_tokens=2),
        )


def test_inference_provider_is_structural_and_task_agnostic() -> None:
    provider = _EchoProvider()
    request = InferenceRequest(
        request_id="request-1",
        input={"text": "hello"},
        response_schema={"type": "object"},
        generation=GenerationConfig(temperature=0.0, max_output_tokens=64, seed=42),
        task_metadata={"task_id": "structured-output"},
    )

    result = provider.generate(request)

    assert isinstance(provider, InferenceProvider)
    assert result.valid is True
    assert result.normalized_output == {"text": "hello"}
    assert result.usage.total_tokens == 5


def test_request_requires_input_or_messages() -> None:
    with pytest.raises(ValueError, match="requires input or messages"):
        InferenceRequest(request_id="empty")


def test_invalid_result_requires_typed_error() -> None:
    with pytest.raises(ValueError, match="require a typed error"):
        InferenceResult(
            provider_id="provider",
            model_id="model",
            raw_output=None,
            latency_ms=0.0,
            valid=False,
        )

    result = InferenceResult(
        provider_id="provider",
        model_id="model",
        raw_output=None,
        latency_ms=0.0,
        valid=False,
        error=InferenceError(kind="timeout", message="timed out", retryable=True),
    )
    assert result.error is not None
    assert result.error.kind == "timeout"
    assert result.error.retryable is True


def test_model_provider_and_runtime_are_separate_contracts() -> None:
    provider = ProviderSpec(
        provider_key="openai-compatible",
        provider_type="openai-compatible",
        base_url_env="MODEL_BASE_URL",
        api_key_env="MODEL_API_KEY",
    )
    runtime = RuntimeSpec(
        runtime_key="local-korgis",
        provider_key=provider.provider_key,
        deployment="local",
        lifecycle="managed",
    )
    model = ModelSpec(
        model_key="qwen-local",
        model_id="qwen/example",
        runtime_key=runtime.runtime_key,
        family="qwen",
        parameters_b=4.0,
        artifact=ArtifactSpec(format="gguf", quantization="Q4_K_M"),
        tags=("local", "classification"),
    )

    assert model.runtime_key == runtime.runtime_key
    assert runtime.provider_key == provider.provider_key
    assert runtime.deployment == "local"
    assert model.artifact is not None
    assert model.artifact.quantization == "Q4_K_M"


def test_run_manifest_keeps_reproducibility_dimensions_explicit() -> None:
    provider = ProviderSpec("provider", "openai-compatible")
    runtime = RuntimeSpec("runtime", "provider", "api")
    model = ModelSpec("model-key", "vendor/model", "runtime")
    context = RunContext(
        run_id="run-1",
        run_group="group-1",
        suite_id="capability-core",
        seed=42,
        profile="budget",
        started_at_utc="2026-09-27T12:00:00+00:00",
    )
    manifest = RunManifest(
        schema_version="1",
        context=context,
        benchmark_core_version="0.1.0",
        model=model,
        runtime=runtime,
        provider=provider,
        task_id="intent-classification",
        task_version="1",
        generation=GenerationConfig(temperature=0.0, seed=42),
        git_commit="abc123",
        prompt_id="intent-v1",
        prompt_version="1",
        dataset_id="banking77",
        dataset_revision="fixture-revision",
        dataset_split="test",
        sample_selection_fingerprint="sha256:fixture",
    )

    payload = asdict(manifest)

    assert payload["context"]["seed"] == 42
    assert payload["model"]["model_id"] == "vendor/model"
    assert payload["runtime"]["deployment"] == "api"
    assert payload["dataset_id"] == "banking77"
    assert payload["prompt_id"] == "intent-v1"
