from __future__ import annotations

from collections.abc import Callable, Mapping

from benchmark_core import InferenceProvider, ResolvedModel

from model_capability_bench.providers.openai_json import (
    OpenAICompatibleJsonProvider,
    OpenAIResponsesJsonProvider,
)

ProviderBuilder = Callable[[ResolvedModel, Mapping[str, str]], InferenceProvider]


class ProviderFactoryError(ValueError):
    """Raised when a configured provider cannot be materialized."""


def _env_value(
    environ: Mapping[str, str],
    name: str | None,
) -> str | None:
    if name is None:
        return None
    value = environ.get(name)
    return value if value else None


def _openai_compatible(
    model: ResolvedModel,
    environ: Mapping[str, str],
) -> InferenceProvider:
    provider = model.provider
    base_url = _env_value(environ, provider.base_url_env)
    if base_url is None:
        configured = provider.options.get("default_base_url")
        base_url = str(configured) if configured else None
    if base_url is None:
        raise ProviderFactoryError(
            f"Provider {provider.provider_key!r} requires a base URL"
        )

    api_key = _env_value(environ, provider.api_key_env) or "local"
    return OpenAICompatibleJsonProvider(
        model,
        base_url=base_url,
        api_key=api_key,
        environ=environ,
    )


def _openai(
    model: ResolvedModel,
    environ: Mapping[str, str],
) -> InferenceProvider:
    provider = model.provider
    api_key = _env_value(environ, provider.api_key_env)
    if api_key is None:
        raise ProviderFactoryError(
            f"Provider {provider.provider_key!r} requires an API key"
        )
    return OpenAIResponsesJsonProvider(
        model,
        api_key=api_key,
        environ=environ,
    )


def _typesafe(
    model: ResolvedModel,
    environ: Mapping[str, str],
) -> InferenceProvider:
    from model_capability_bench.providers.typesafe_json import TypeSafeJevJsonProvider

    provider = model.provider
    api_key = _env_value(environ, provider.api_key_env)
    if api_key is None:
        raise ProviderFactoryError(
            f"Provider {provider.provider_key!r} requires an API key"
        )
    return TypeSafeJevJsonProvider(
        model,
        api_key=api_key,
        environ=environ,
    )


def _decisio(
    model: ResolvedModel,
    environ: Mapping[str, str],
) -> InferenceProvider:
    from model_capability_bench.providers.decisio_json import DecisioJsonProvider

    return DecisioJsonProvider(
        model,
        environ=environ,
    )


DEFAULT_PROVIDER_BUILDERS: Mapping[str, ProviderBuilder] = {
    "openai-compatible": _openai_compatible,
    "openai": _openai,
    "typesafe": _typesafe,
    "decisio": _decisio,
}


def build_inference_provider(
    model: ResolvedModel,
    environ: Mapping[str, str],
    *,
    builders: Mapping[str, ProviderBuilder] = DEFAULT_PROVIDER_BUILDERS,
) -> InferenceProvider:
    provider_type = model.provider.provider_type
    try:
        builder = builders[provider_type]
    except KeyError as exc:
        raise ProviderFactoryError(
            f"Unsupported provider type: {provider_type!r}"
        ) from exc

    protocol = str(model.provider.options.get("protocol") or "")
    if (
        provider_type == "openai-compatible"
        and protocol != "chat-completions"
    ):
        raise ProviderFactoryError(
            f"Provider {model.provider.provider_key!r} uses unsupported "
            f"protocol {protocol!r}"
        )
    if provider_type == "openai" and protocol != "responses":
        raise ProviderFactoryError(
            f"Provider {model.provider.provider_key!r} uses unsupported "
            f"protocol {protocol!r}"
        )
    if provider_type == "typesafe" and protocol != "system-one":
        raise ProviderFactoryError(
            f"Provider {model.provider.provider_key!r} uses unsupported "
            f"protocol {protocol!r}"
        )
    if provider_type == "decisio" and protocol != "decisio-engine":
        raise ProviderFactoryError(
            f"Provider {model.provider.provider_key!r} uses unsupported "
            f"protocol {protocol!r}"
        )
    return builder(model, environ)

