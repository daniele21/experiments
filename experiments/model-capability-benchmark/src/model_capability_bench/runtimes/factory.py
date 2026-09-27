from __future__ import annotations

from collections.abc import Mapping
from typing import Callable

from benchmark_core import ResolvedModel

from model_capability_bench.providers import build_inference_provider
from model_capability_bench.runner.contracts import ModelRuntime
from model_capability_bench.runtimes.external import ExternalProviderRuntime
from model_capability_bench.runtimes.korgis import KorgisManagedRuntime

RuntimeBuilder = Callable[[ResolvedModel], ModelRuntime]


class RuntimeFactoryError(ValueError):
    """Raised when a configured runtime cannot be materialized."""


class RegistryRuntimeResolver:
    def __init__(
        self,
        environ: Mapping[str, str],
    ) -> None:
        self.environ = environ
        self._instances: dict[str, ModelRuntime] = {}

    def __call__(self, model: ResolvedModel) -> ModelRuntime:
        runtime_key = model.runtime.runtime_key
        existing = self._instances.get(runtime_key)
        if existing is not None:
            return existing

        runtime_type = str(model.runtime.options.get("runtime_type") or "")
        if runtime_type == "korgis":
            runtime: ModelRuntime = KorgisManagedRuntime(
                environ=self.environ,
                provider_builder=build_inference_provider,
            )
        elif runtime_type == "provider-api":
            runtime = ExternalProviderRuntime(
                environ=self.environ,
                provider_builder=build_inference_provider,
            )
        else:
            raise RuntimeFactoryError(
                f"Unsupported runtime type {runtime_type!r} for "
                f"{runtime_key!r}"
            )

        self._instances[runtime_key] = runtime
        return runtime
