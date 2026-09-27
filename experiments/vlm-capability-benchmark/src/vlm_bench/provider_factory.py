from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark_core import ConfigError, JsonHttpTransport

from vlm_bench.config import ResolvedVLMModel
from vlm_bench.providers import OpenAICompatibleVLMProvider


def create_vlm_provider(
    model: ResolvedVLMModel,
    *,
    environ: Mapping[str, str],
) -> Any:
    if model.provider_type != "openai-compatible":
        raise ConfigError(
            f"{model.model_key}: unsupported provider type {model.provider_type!r}"
        )
    base_url = environ.get(model.base_url_env, "").strip()
    if not base_url:
        raise ConfigError(
            f"{model.model_key}: missing endpoint environment variable "
            f"{model.base_url_env}"
        )
    api_key = (
        environ.get(model.api_key_env, "").strip()
        if model.api_key_env is not None
        else None
    )
    return OpenAICompatibleVLMProvider(
        model_id=model.model_id,
        base_url=base_url,
        api_key=api_key or None,
        transport=JsonHttpTransport(model.transport_policy),
    )
