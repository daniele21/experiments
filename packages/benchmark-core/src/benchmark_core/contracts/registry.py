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
class ModelCapabilities:
    text_input: bool = True
    image_input: bool = False
    image_output: bool = False
    image_editing: bool = False
    multi_image_input: bool = False

    def missing(self, required: "ModelCapabilities") -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "text_input",
                "image_input",
                "image_output",
                "image_editing",
                "multi_image_input",
            )
            if getattr(required, name) and not getattr(self, name)
        )


@dataclass(frozen=True)
class ProviderSpec:
    provider_key: str
    provider_type: str
    base_url_env: str | None = None
    api_key_env: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.provider_key, "provider_key")
        _require_identifier(self.provider_type, "provider_type")


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


@dataclass(frozen=True)
class ModelSpec:
    model_key: str
    model_id: str
    runtime_key: str
    family: str | None = None
    parameters_b: float | None = None
    artifact: ArtifactSpec | None = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.model_key, "model_key")
        _require_identifier(self.model_id, "model_id")
        _require_identifier(self.runtime_key, "runtime_key")
        if self.parameters_b is not None and self.parameters_b <= 0:
            raise ValueError("parameters_b must be > 0")
