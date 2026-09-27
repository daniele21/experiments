from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark_core import ConfigError, TransportPolicy, load_yaml_section


@dataclass(frozen=True)
class ResolvedVLMModel:
    model_key: str
    model_id: str
    runtime_key: str
    provider_key: str
    provider_type: str
    base_url_env: str
    api_key_env: str | None
    transport_policy: TransportPolicy


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{context} must be a mapping")
    return {str(key): item for key, item in value.items()}


def resolve_vlm_models(
    root: Path,
    model_keys: Sequence[str],
) -> tuple[ResolvedVLMModel, ...]:
    models = load_yaml_section(root / "models.yaml", "models", required=True)
    runtimes = load_yaml_section(root / "runtimes.yaml", "runtimes", required=True)
    providers = load_yaml_section(root / "runtimes.yaml", "providers", required=True)

    resolved: list[ResolvedVLMModel] = []
    for model_key in model_keys:
        if model_key not in models:
            raise ConfigError(f"Unknown VLM model: {model_key}")
        model = _mapping(models[model_key], context=f"model {model_key!r}")
        runtime_key = str(model.get("runtime", "")).strip()
        if runtime_key not in runtimes:
            raise ConfigError(f"{model_key}: unknown runtime {runtime_key!r}")
        runtime = _mapping(runtimes[runtime_key], context=f"runtime {runtime_key!r}")
        provider_key = str(runtime.get("provider", "")).strip()
        if provider_key not in providers:
            raise ConfigError(f"{runtime_key}: unknown provider {provider_key!r}")
        provider = _mapping(providers[provider_key], context=f"provider {provider_key!r}")
        transport = _mapping(
            runtime.get("transport"),
            context=f"runtime {runtime_key!r} transport",
        )
        capabilities = _mapping(
            model.get("capabilities"),
            context=f"model {model_key!r} capabilities",
        )
        if not bool(capabilities.get("image_input")):
            raise ConfigError(f"{model_key}: image_input capability is required")

        model_id = str(model.get("model_id", "")).strip()
        provider_type = str(provider.get("type", "")).strip()
        base_url_env = str(provider.get("base_url_env", "")).strip()
        if not model_id or not provider_type or not base_url_env:
            raise ConfigError(
                f"{model_key}: model_id, provider type and base_url_env are required"
            )

        raw_api_key_env = provider.get("api_key_env")
        api_key_env = str(raw_api_key_env).strip() if raw_api_key_env else None
        resolved.append(
            ResolvedVLMModel(
                model_key=model_key,
                model_id=model_id,
                runtime_key=runtime_key,
                provider_key=provider_key,
                provider_type=provider_type,
                base_url_env=base_url_env,
                api_key_env=api_key_env,
                transport_policy=TransportPolicy(
                    max_retries=int(transport["max_retries"]),
                    timeout_seconds=float(transport["timeout_seconds"]),
                ),
            )
        )
    return tuple(resolved)
