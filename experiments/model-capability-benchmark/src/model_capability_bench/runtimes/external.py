from __future__ import annotations

from collections.abc import Callable, Mapping

from benchmark_core import InferenceProvider, ResolvedModel

ProviderBuilder = Callable[[ResolvedModel, Mapping[str, str]], InferenceProvider]


class ExternalProviderRuntime:
    def __init__(
        self,
        *,
        environ: Mapping[str, str],
        provider_builder: ProviderBuilder,
    ) -> None:
        self.environ = environ
        self.provider_builder = provider_builder
        self._active_providers: list[InferenceProvider] = []

    def prepare(self, model: ResolvedModel) -> InferenceProvider:
        provider = self.provider_builder(model, self.environ)
        self._active_providers.append(provider)
        return provider

    def release(self, model: ResolvedModel) -> None:
        while self._active_providers:
            provider = self._active_providers.pop()
            closer = getattr(provider, "close", None) or getattr(provider, "release", None)
            if callable(closer):
                closer()
        return None
