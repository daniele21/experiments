from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core.config import load_yaml_mapping
from benchmark_core.contracts import ArtifactSpec, ModelSpec, ProviderSpec, RuntimeSpec
from benchmark_core.registry.models import RegistryBundle, RegistryError


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RegistryError(f"{context} must be a mapping")
    return value


def _tuple_of_strings(value: Any, *, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RegistryError(f"{context} must be a list")
    return tuple(str(item) for item in value)


def _options(value: Any, *, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(k): v for k, v in _mapping(value, context=context).items()}


def _reject_unknown_keys(
    raw: Mapping[str, Any],
    *,
    allowed: set[str],
    context: str,
) -> None:
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise RegistryError(
            f"{context} contains unsupported fields: {', '.join(unknown)}"
        )


def _provider(key: str, raw: Mapping[str, Any]) -> ProviderSpec:
    _reject_unknown_keys(
        raw,
        allowed={
            "type",
            "provider_type",
            "base_url_env",
            "api_key_env",
            "required_env",
            "options",
        },
        context=f"provider {key!r}",
    )
    provider_type = str(raw.get("type") or raw.get("provider_type") or "")
    return ProviderSpec(
        provider_key=key,
        provider_type=provider_type,
        base_url_env=(
            str(raw["base_url_env"]) if raw.get("base_url_env") is not None else None
        ),
        api_key_env=(
            str(raw["api_key_env"]) if raw.get("api_key_env") is not None else None
        ),
        required_env=_tuple_of_strings(
            raw.get("required_env"),
            context=f"provider {key!r} required_env",
        ),
        options=_options(raw.get("options"), context=f"provider {key!r} options"),
    )


def _runtime(key: str, raw: Mapping[str, Any]) -> RuntimeSpec:
    _reject_unknown_keys(
        raw,
        allowed={"provider", "provider_key", "deployment", "lifecycle", "options"},
        context=f"runtime {key!r}",
    )
    return RuntimeSpec(
        runtime_key=key,
        provider_key=str(raw.get("provider") or raw.get("provider_key") or ""),
        deployment=str(raw.get("deployment") or ""),
        lifecycle=str(raw.get("lifecycle") or "external"),
        options=_options(raw.get("options"), context=f"runtime {key!r} options"),
    )


def _artifact(raw: Any, *, model_key: str) -> ArtifactSpec | None:
    if raw is None:
        return None
    data = _mapping(raw, context=f"model {model_key!r} artifact")
    _reject_unknown_keys(
        data,
        allowed={"format", "quantization", "size_bytes", "source", "metadata"},
        context=f"model {model_key!r} artifact",
    )
    return ArtifactSpec(
        format=str(data.get("format") or ""),
        quantization=(
            str(data["quantization"]) if data.get("quantization") is not None else None
        ),
        size_bytes=(
            int(data["size_bytes"]) if data.get("size_bytes") is not None else None
        ),
        source=str(data["source"]) if data.get("source") is not None else None,
        metadata=_options(
            data.get("metadata"),
            context=f"model {model_key!r} artifact metadata",
        ),
    )


def _model(key: str, raw: Mapping[str, Any]) -> ModelSpec:
    _reject_unknown_keys(
        raw,
        allowed={
            "model_id",
            "runtime",
            "runtime_key",
            "runtime_model_id",
            "family",
            "parameters_b",
            "artifact",
            "tags",
            "metadata",
        },
        context=f"model {key!r}",
    )
    return ModelSpec(
        model_key=key,
        model_id=str(raw.get("model_id") or ""),
        runtime_key=str(raw.get("runtime") or raw.get("runtime_key") or ""),
        runtime_model_id=(
            str(raw["runtime_model_id"])
            if raw.get("runtime_model_id") is not None
            else None
        ),
        family=str(raw["family"]) if raw.get("family") is not None else None,
        parameters_b=(
            float(raw["parameters_b"]) if raw.get("parameters_b") is not None else None
        ),
        artifact=_artifact(raw.get("artifact"), model_key=key),
        tags=_tuple_of_strings(raw.get("tags"), context=f"model {key!r} tags"),
        metadata=_options(raw.get("metadata"), context=f"model {key!r} metadata"),
    )


def load_registry(path: Path) -> RegistryBundle:
    payload = load_yaml_mapping(path, required=True)

    providers_raw = _mapping(payload.get("providers"), context="providers")
    runtimes_raw = _mapping(payload.get("runtimes"), context="runtimes")
    models_raw = _mapping(payload.get("models"), context="models")

    providers = {
        str(key): _provider(
            str(key),
            _mapping(raw, context=f"provider {key!r}"),
        )
        for key, raw in providers_raw.items()
    }
    runtimes = {
        str(key): _runtime(
            str(key),
            _mapping(raw, context=f"runtime {key!r}"),
        )
        for key, raw in runtimes_raw.items()
    }
    models = {
        str(key): _model(
            str(key),
            _mapping(raw, context=f"model {key!r}"),
        )
        for key, raw in models_raw.items()
    }

    if not providers:
        raise RegistryError("Registry must define at least one provider")
    if not runtimes:
        raise RegistryError("Registry must define at least one runtime")
    if not models:
        raise RegistryError("Registry must define at least one model")

    return RegistryBundle(
        providers=providers,
        runtimes=runtimes,
        models=models,
    )
