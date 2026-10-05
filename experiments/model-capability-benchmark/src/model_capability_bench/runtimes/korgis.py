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

_KORGIS_RUNTIME_OVERRIDE_KEYS = {
    "backend",
    "ctx_size",
    "max_kv_size",
    "n_gpu_layers",
    "n_threads",
    "n_batch",
    "n_ubatch",
    "offload_kqv",
    "flash_attn",
    "use_mmap",
    "timeout",
    "startup_timeout",
    "max_concurrent_requests",
    "enable_thinking",
    "show_thinking",
}


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
        self.resource_transport = JsonHttpTransport(
            TransportPolicy(
                max_retries=0,
                timeout_seconds=min(timeout_seconds, 2.0),
            )
        )

    def health(self) -> dict[str, Any]:
        payload = self.transport.request("GET", f"{self.root}/health").body
        if not isinstance(payload, dict):
            raise TypeError("Korgis health response must be an object")
        return payload

    def resources(self) -> dict[str, Any]:
        payload = self.resource_transport.request(
            "GET",
            f"{self.root}/api/v1/resources",
        ).body
        if not isinstance(payload, dict):
            raise TypeError("Korgis resources response must be an object")
        return payload

    def activate(
        self,
        model_key: str,
        runtime_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_body: dict[str, Any] = {"model": model_key}
        if runtime_config:
            payload_body.update(dict(runtime_config))
        payload = self.transport.request(
            "POST",
            f"{self.root}/api/v1/models/activate",
            payload=payload_body,
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
        self._activation_by_model: dict[str, dict[str, Any]] = {}
        self._runtime_config: dict[str, Any] = {}
        self._effective_runtime_config_by_model: dict[str, dict[str, Any]] = {}

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

    def configure(self, runtime_config: Mapping[str, object]) -> None:
        config = dict(runtime_config)
        unknown = sorted(set(config) - _KORGIS_RUNTIME_OVERRIDE_KEYS)
        if unknown:
            raise ValueError(
                "Unsupported Korgis runtime override keys: " + ", ".join(unknown)
            )
        self._runtime_config = config

    def prepare(self, model: ResolvedModel) -> InferenceProvider:
        control = self._control(model)
        health = control.health()
        if not health.get("ok"):
            raise RuntimeError(
                f"Korgis runtime {model.runtime.runtime_key!r} is not healthy"
            )
        activation = control.activate(
            model.effective_model_id,
            self._runtime_config,
        )
        if activation.get("ok") is False:
            raise RuntimeError(
                f"Korgis failed to activate {model.effective_model_id!r}: "
                f"{activation}"
            )
        effective_health = control.health()
        if not effective_health.get("ok"):
            raise RuntimeError(
                f"Korgis runtime {model.runtime.runtime_key!r} became unhealthy "
                "after activation"
            )
        effective_runtime_config = {
            key: effective_health.get(key)
            for key in _KORGIS_RUNTIME_OVERRIDE_KEYS
            if key in effective_health
        }
        for key, requested in self._runtime_config.items():
            actual = effective_runtime_config.get(key)
            if actual is not None and actual != requested:
                raise RuntimeError(
                    f"Korgis runtime override {key!r} was not applied: "
                    f"requested={requested!r}, actual={actual!r}"
                )
        self._activation_by_model[model.model.model_key] = dict(activation)
        self._effective_runtime_config_by_model[model.model.model_key] = (
            effective_runtime_config
        )
        provider = self.provider_builder(model, self.environ)
        telemetry_enabled = self.environ.get(
            "MCB_RESOURCE_TELEMETRY",
            "1",
        ).strip().lower() not in {"0", "false", "no", "off"}
        if not telemetry_enabled:
            return provider

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

    def execution_metadata(self, model: ResolvedModel) -> dict[str, Any]:
        activation = self._activation_by_model.get(model.model.model_key) or {}
        metadata: dict[str, Any] = {"runtime_source": "korgis"}

        runtime_identity = activation.get("runtime_identity")
        if isinstance(runtime_identity, Mapping):
            metadata["runtime_identity"] = dict(runtime_identity)

        cfg = activation.get("cfg")
        if isinstance(cfg, Mapping):
            for key in ("backend", "quantization"):
                value = cfg.get(key)
                if value is not None:
                    metadata[key] = value

        activation_key = activation.get("key")
        if activation_key:
            metadata["runtime_key"] = str(activation_key)
        effective = self._effective_runtime_config_by_model.get(
            model.model.model_key
        )
        if effective:
            metadata["runtime_config"] = dict(effective)
        return metadata

    def release(self, model: ResolvedModel) -> None:
        control = self._control(model)
        unloaded = control.unload(model.effective_model_id)
        if unloaded.get("ok") is False:
            raise RuntimeError(
                f"Korgis failed to unload {model.effective_model_id!r}: {unloaded}"
            )
        self._activation_by_model.pop(model.model.model_key, None)
        self._effective_runtime_config_by_model.pop(model.model.model_key, None)
        self._runtime_config = {}
