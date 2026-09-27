from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from benchmark_core.contracts import ModelSpec, ProviderSpec, RuntimeSpec


class RegistryError(ValueError):
    """Raised when model/runtime/provider registry configuration is invalid."""


@dataclass(frozen=True)
class ResolvedModel:
    model: ModelSpec
    runtime: RuntimeSpec
    provider: ProviderSpec

    @property
    def effective_model_id(self) -> str:
        return self.model.runtime_model_id or self.model.model_id


@dataclass(frozen=True)
class RegistryBundle:
    providers: Mapping[str, ProviderSpec]
    runtimes: Mapping[str, RuntimeSpec]
    models: Mapping[str, ModelSpec]

    def __post_init__(self) -> None:
        for runtime_key, runtime in self.runtimes.items():
            if runtime.provider_key not in self.providers:
                raise RegistryError(
                    f"Runtime {runtime_key!r} references unknown provider "
                    f"{runtime.provider_key!r}"
                )
        for model_key, model in self.models.items():
            if model.runtime_key not in self.runtimes:
                raise RegistryError(
                    f"Model {model_key!r} references unknown runtime "
                    f"{model.runtime_key!r}"
                )

    def resolve(self, model_key: str) -> ResolvedModel:
        try:
            model = self.models[model_key]
        except KeyError as exc:
            raise RegistryError(f"Unknown model key: {model_key}") from exc
        runtime = self.runtimes[model.runtime_key]
        provider = self.providers[runtime.provider_key]
        return ResolvedModel(model=model, runtime=runtime, provider=provider)

    def select(
        self,
        *,
        model_keys: Sequence[str] | None = None,
        tags: Sequence[str] = (),
        deployment: str | None = None,
        family: str | None = None,
        max_parameters_b: float | None = None,
        quantization: str | None = None,
    ) -> list[ResolvedModel]:
        if model_keys is None:
            keys = list(self.models)
        else:
            keys = list(dict.fromkeys(model_keys))

        required_tags = set(tags)
        selected: list[ResolvedModel] = []
        for key in keys:
            resolved = self.resolve(key)
            model = resolved.model
            runtime = resolved.runtime

            if required_tags and not required_tags.issubset(set(model.tags)):
                continue
            if deployment is not None and runtime.deployment != deployment:
                continue
            if family is not None and model.family != family:
                continue
            if (
                max_parameters_b is not None
                and (
                    model.parameters_b is None
                    or model.parameters_b > max_parameters_b
                )
            ):
                continue
            if (
                quantization is not None
                and (
                    model.artifact is None
                    or model.artifact.quantization != quantization
                )
            ):
                continue
            selected.append(resolved)

        return selected


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    message: str
    model_key: str | None = None
    runtime_key: str | None = None
    provider_key: str | None = None
    env_var: str | None = None


@dataclass(frozen=True)
class PreflightResult:
    issues: tuple[PreflightIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues

    def raise_for_errors(self) -> None:
        if self.ok:
            return
        rendered = "; ".join(issue.message for issue in self.issues)
        raise RegistryError(f"Registry preflight failed: {rendered}")


def preflight_models(
    registry: RegistryBundle,
    models: Sequence[ResolvedModel],
    environ: Mapping[str, str],
) -> PreflightResult:
    issues: list[PreflightIssue] = []
    checked_providers: set[str] = set()

    for resolved in models:
        registered = registry.models.get(resolved.model.model_key)
        if registered != resolved.model:
            raise RegistryError(
                f"Resolved model {resolved.model.model_key!r} does not belong to this registry"
            )

        provider = resolved.provider
        if provider.provider_key in checked_providers:
            continue
        checked_providers.add(provider.provider_key)

        for env_var in provider.required_env:
            name = str(env_var)
            if not environ.get(name):
                issues.append(
                    PreflightIssue(
                        code="missing_env",
                        message=(
                            f"Provider {provider.provider_key!r} requires environment "
                            f"variable {name!r}"
                        ),
                        model_key=resolved.model.model_key,
                        runtime_key=resolved.runtime.runtime_key,
                        provider_key=provider.provider_key,
                        env_var=name,
                    )
                )

    return PreflightResult(tuple(issues))


def registry_summary(registry: RegistryBundle) -> dict[str, Any]:
    return {
        "providers": len(registry.providers),
        "runtimes": len(registry.runtimes),
        "models": len(registry.models),
        "deployments": sorted(
            {runtime.deployment for runtime in registry.runtimes.values()}
        ),
    }
