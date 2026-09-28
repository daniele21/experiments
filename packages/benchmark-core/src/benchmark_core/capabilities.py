from __future__ import annotations

from benchmark_core.contracts.registry import ModelCapabilities, ModelSpec


class CapabilityMismatchError(ValueError):
    """Raised when a model cannot satisfy a task's declared requirements."""


def validate_model_capabilities(
    model: ModelSpec,
    required: ModelCapabilities,
) -> None:
    missing = model.capabilities.missing(required)
    if not missing:
        return
    joined = ", ".join(missing)
    raise CapabilityMismatchError(
        f"model {model.model_key!r} does not support required capabilities: {joined}"
    )
