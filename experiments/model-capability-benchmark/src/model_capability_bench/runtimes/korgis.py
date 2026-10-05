from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from benchmark_core import (
    InferenceProvider,
    JsonHttpTransport,
    ResolvedModel,
    TransportPolicy,
)

from model_capability_bench.telemetry.resources import ResourceSamplingProvider

ProviderBuilder = Callable[[ResolvedModel, Mapping[str, str]], InferenceProvider]


class KorgisControlClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_base = base_url.rstrip("/")
        self.root = self.api_base.removesuffix("/v1")
        self.transport = JsonHttpTransport(
            TransportPolicy(max_retries=0, timeout_seconds=timeout_seconds)
        )

    def health(self) -> dict[str, Any]:
        payload = self.transport.request("GET", f"{self.root}/health").body
        if not isinstance(payload, dict):
            raise TypeError("Korgis health response must be an object")
        return payload

    def resources(self) -> dict[str, Any]:
        payload = self.transport.request(
            "GET",
            f"{self.root}/api/v1/resources",
        ).body
        if not isinstance(payload, dict):
            raise TypeError("Korgis resources response must be an object")
        return payload

    def activate(self, model_key: str) -> dict[str, Any]:
        payload = self.transport.request(
            "POST",
            f"{self.root}/api/v1/models/activate",
            payload={"model": model_key},
        ).body
        if not isinstance(payload, dict):
            raise TypeError("Korgis activate response must be an object")
        return payload

    def unload(self, model_key: str) -> dict[str, Any]:
        payload = self.transport.request(
            "DELETE",
            f"{self.root}/api/v1/models/{model_key}",
        ).body
        if not isinstance(payload, dict):
            raise TypeError("Korgis unload response must be an object")
        return payload


class KorgisManagedRuntime:
    def __init__(
        self,
        *,
        environ: Mapping[str, str],
        provider_builder: ProviderBuilder,
        control_factory: Callable[..., KorgisControlClient] = KorgisControlClient,
    ) -> None:
        self.environ = environ
        self.provider_builder = provider_builder
        self.control_factory = control_factory
        self._control_by_runtime: dict[str, KorgisControlClient] = {}

    def _control(self, model: ResolvedModel) -> KorgisControlClient:
        runtime_key = model.runtime.runtime_key
        existing = self._control_by_runtime.get(runtime_key)
        if existing is not None:
            return existing

        provider = model.provider
        if provider.base_url_env is None:
            raise ValueError(
                f"Korgis provider {provider.provider_key!r} has no base_url_env"
            )
        base_url = self.environ.get(provider.base_url_env)
        if not base_url:
            raise ValueError(
                f"Korgis provider {provider.provider_key!r} requires "
                f"{provider.base_url_env!r}"
            )

        timeout_env = str(
            model.runtime.options.get("control_timeout_env")
            or "KORGIS_CONTROL_TIMEOUT_SECONDS"
        )
        timeout_seconds = float(self.environ.get(timeout_env, "360"))
        control = self.control_factory(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self._control_by_runtime[runtime_key] = control
        return control

    def prepare(self, model: ResolvedModel) -> InferenceProvider:
        control = self._control(model)
        health = control.health()
        if not health.get("ok"):
            raise RuntimeError(
                f"Korgis runtime {model.runtime.runtime_key!r} is not healthy"
            )
        activation = control.activate(model.effective_model_id)
        if activation.get("ok") is False:
            raise RuntimeError(
                f"Korgis failed to activate {model.effective_model_id!r}: "
                f"{activation}"
            )
        provider = self.provider_builder(model, self.environ)
        interval_ms = float(
            self.environ.get("MCB_RESOURCE_SAMPLE_INTERVAL_MS", "250")
        )
        if interval_ms <= 0:
            raise ValueError("MCB_RESOURCE_SAMPLE_INTERVAL_MS must be > 0")
        return ResourceSamplingProvider(
            provider,
            fetch=control.resources,
            runtime_aliases=(
                model.effective_model_id,
                model.model.model_id,
                model.model.model_key,
            ),
            interval_seconds=interval_ms / 1000.0,
        )

    def release(self, model: ResolvedModel) -> None:
        control = self._control(model)
        unloaded = control.unload(model.effective_model_id)
        if unloaded.get("ok") is False:
            raise RuntimeError(
                f"Korgis failed to unload {model.effective_model_id!r}: {unloaded}"
            )
