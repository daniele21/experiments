from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from benchmark_core import ArtifactStore, ConfigError, JsonHttpTransport

from imagegen_bench.config import ResolvedImageModel
from imagegen_bench.providers import (
    GeminiImageProvider,
    KorgisImageProvider,
    OpenAIImageProvider,
    create_gemini_image_client,
    create_openai_image_client,
)


def _required_env(
    model: ResolvedImageModel,
    environ: Mapping[str, str],
    env_name: str | None,
    *,
    purpose: str,
) -> str:
    if not env_name:
        raise ConfigError(f"{model.model_key}: {purpose} environment variable is not configured")
    value = environ.get(env_name, "").strip()
    if not value:
        raise ConfigError(f"{model.model_key}: missing {purpose} environment variable {env_name}")
    return value


def _openai_provider(
    model: ResolvedImageModel,
    store: ArtifactStore,
    environ: Mapping[str, str],
) -> OpenAIImageProvider:
    api_key = _required_env(model, environ, model.api_key_env, purpose="credential")
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
    environ: Mapping[str, str],
) -> GeminiImageProvider:
    api_key = _required_env(model, environ, model.api_key_env, purpose="credential")
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


def _korgis_provider(
    model: ResolvedImageModel,
    store: ArtifactStore,
    environ: Mapping[str, str],
) -> KorgisImageProvider:
    base_url = _required_env(model, environ, model.base_url_env, purpose="endpoint")
    api_key = (
        environ.get(model.api_key_env, "").strip()
        if model.api_key_env is not None
        else None
    )
    return KorgisImageProvider(
        model_id=model.model_id,
        base_url=base_url,
        transport=JsonHttpTransport(model.transport_policy),
        artifact_store=store,
        generation_options=model.generation,
        api_key=api_key or None,
    )


_PROVIDER_BUILDERS: dict[
    str,
    Callable[[ResolvedImageModel, ArtifactStore, Mapping[str, str]], Any],
] = {
    "openai-image": _openai_provider,
    "gemini-image": _gemini_provider,
    "korgis-image": _korgis_provider,
}


def create_image_provider(
    model: ResolvedImageModel,
    *,
    artifact_store: ArtifactStore,
    environ: Mapping[str, str],
) -> Any:
    try:
        builder = _PROVIDER_BUILDERS[model.provider_type]
    except KeyError as exc:
        raise ConfigError(
            f"{model.model_key}: unsupported provider type {model.provider_type!r}"
        ) from exc
    return builder(model, artifact_store, environ)
