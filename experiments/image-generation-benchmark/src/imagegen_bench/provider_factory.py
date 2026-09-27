from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from benchmark_core import ArtifactStore, ConfigError

from imagegen_bench.config import ResolvedImageModel
from imagegen_bench.providers import (
    GeminiImageProvider,
    OpenAIImageProvider,
    create_gemini_image_client,
    create_openai_image_client,
)


def _openai_provider(
    model: ResolvedImageModel,
    store: ArtifactStore,
    api_key: str,
) -> OpenAIImageProvider:
    return OpenAIImageProvider(
        model_id=model.model_id,
        client=create_openai_image_client(
            api_key=api_key,
            policy=model.transport_policy,
        ),
        artifact_store=store,
        generation_options=model.generation,
    )


def _gemini_provider(
    model: ResolvedImageModel,
    store: ArtifactStore,
    api_key: str,
) -> GeminiImageProvider:
    response_format = model.generation.get("response_format")
    if not isinstance(response_format, Mapping):
        raise ConfigError(f"{model.model_key}: Gemini response_format is required")
    generation_config = model.generation.get("generation_config")
    if generation_config is not None and not isinstance(generation_config, Mapping):
        raise ConfigError(f"{model.model_key}: generation_config must be a mapping")
    return GeminiImageProvider(
        model_id=model.model_id,
        client=create_gemini_image_client(
            api_key=api_key,
            policy=model.transport_policy,
        ),
        artifact_store=store,
        response_format=response_format,
        generation_config=generation_config,
    )


_PROVIDER_BUILDERS: dict[
    str,
    Callable[[ResolvedImageModel, ArtifactStore, str], Any],
] = {
    "openai-image": _openai_provider,
    "gemini-image": _gemini_provider,
}


def create_image_provider(
    model: ResolvedImageModel,
    *,
    artifact_store: ArtifactStore,
    environ: Mapping[str, str],
) -> Any:
    api_key = environ.get(model.api_key_env, "").strip()
    if not api_key:
        raise ConfigError(
            f"{model.model_key}: missing credential environment variable "
            f"{model.api_key_env}"
        )
    try:
        builder = _PROVIDER_BUILDERS[model.provider_type]
    except KeyError as exc:
        raise ConfigError(
            f"{model.model_key}: unsupported provider type {model.provider_type!r}"
        ) from exc
    return builder(model, artifact_store, api_key)
