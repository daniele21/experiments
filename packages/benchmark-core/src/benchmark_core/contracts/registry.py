from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

DeploymentMode = Literal["local", "api", "remote", "hybrid"]
LifecycleMode = Literal["external", "managed", "persistent"]


def _require_identifier(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class ArtifactSpec:
    format: str
    quantization: str | None = None
    size_bytes: int | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.format, "format")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")


@dataclass(frozen=True)
class ProviderSpec:
    provider_key: str
    provider_type: str
    base_url_env: str | None = None
    api_key_env: str | None = None
    required_env: tuple[str, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.provider_key, "provider_key")
        _require_identifier(self.provider_type, "provider_type")
        for env_var in self.required_env:
            _require_identifier(env_var, "required_env item")


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_key: str
    provider_key: str
    deployment: DeploymentMode
    lifecycle: LifecycleMode = "external"
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.runtime_key, "runtime_key")
        _require_identifier(self.provider_key, "provider_key")
        if self.deployment not in {"local", "api", "remote", "hybrid"}:
            raise ValueError(f"Unsupported deployment: {self.deployment}")
        if self.lifecycle not in {"external", "managed", "persistent"}:
            raise ValueError(f"Unsupported lifecycle: {self.lifecycle}")


@dataclass(frozen=True)
class ModelSpec:
    model_key: str
    model_id: str
    runtime_key: str
    runtime_model_id: str | None = None
    family: str | None = None
    parameters_b: float | None = None
    artifact: ArtifactSpec | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.model_key, "model_key")
        _require_identifier(self.model_id, "model_id")
        _require_identifier(self.runtime_key, "runtime_key")
        if self.runtime_model_id is not None:
            _require_identifier(self.runtime_model_id, "runtime_model_id")
        if self.parameters_b is not None and self.parameters_b <= 0:
            raise ValueError("parameters_b must be > 0")
