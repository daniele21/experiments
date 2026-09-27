from __future__ import annotations

from collections.abc import Mapping
from typing import Callable

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

    def prepare(self, model: ResolvedModel) -> InferenceProvider:
        return self.provider_builder(model, self.environ)

    def release(self, model: ResolvedModel) -> None:
        return None
