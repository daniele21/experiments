from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core.config import load_yaml_mapping
from benchmark_core.contracts import GenerationConfig
from benchmark_core.suites.contracts import (
    BenchmarkSuiteSpec,
    CapabilityMetricSpec,
    CapabilitySpec,
)


class SuiteConfigError(ValueError):
    """Raised when a benchmark suite declaration is invalid."""


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SuiteConfigError(f"{context} must be a mapping")
    return value


def _reject_unknown(
    raw: Mapping[str, Any],
    *,
    allowed: set[str],
    context: str,
) -> None:
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise SuiteConfigError(
            f"{context} contains unsupported fields: {', '.join(unknown)}"
        )


def _strings(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SuiteConfigError(f"{context} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise SuiteConfigError(f"{context} must contain non-empty strings")
    return tuple(str(item) for item in value)


def _metric(raw: Any, *, capability_id: str, index: int) -> CapabilityMetricSpec:
    data = _mapping(raw, context=f"capability {capability_id!r} metric {index}")
    _reject_unknown(
        data,
        allowed={"name", "source", "reducer", "field", "primary", "options"},
        context=f"capability {capability_id!r} metric {index}",
    )
    primary = data.get("primary", False)
    if not isinstance(primary, bool):
        raise SuiteConfigError(
            f"capability {capability_id!r} metric {index} primary must be boolean"
        )
    options = data.get("options") or {}
    return CapabilityMetricSpec(
        name=str(data.get("name") or ""),
        source=str(data.get("source") or ""),
        reducer=str(data.get("reducer") or ""),
        field=str(data["field"]) if data.get("field") is not None else None,
        primary=primary,
        options=dict(_mapping(options, context="metric options")),
    )


def _capability(capability_id: str, raw: Mapping[str, Any]) -> CapabilitySpec:
    _reject_unknown(
        raw,
        allowed={"task", "task_id", "datasets", "metrics", "description", "tags", "options"},
        context=f"capability {capability_id!r}",
    )
    metrics_raw = raw.get("metrics")
    if not isinstance(metrics_raw, list):
        raise SuiteConfigError(f"capability {capability_id!r} metrics must be a list")
    tags_raw = raw.get("tags") or []
    if not isinstance(tags_raw, list):
        raise SuiteConfigError(f"capability {capability_id!r} tags must be a list")
    options = raw.get("options") or {}
    return CapabilitySpec(
        capability_id=capability_id,
        task_id=str(raw.get("task") or raw.get("task_id") or ""),
        dataset_ids=_strings(
            raw.get("datasets"),
            context=f"capability {capability_id!r} datasets",
        ),
        metrics=tuple(
            _metric(metric, capability_id=capability_id, index=index)
            for index, metric in enumerate(metrics_raw)
        ),
        description=(
            str(raw["description"]) if raw.get("description") is not None else None
        ),
        tags=tuple(str(tag) for tag in tags_raw),
        options=dict(
            _mapping(options, context=f"capability {capability_id!r} options")
        ),
    )


def _generation(raw: Any) -> GenerationConfig:
    data = _mapping(raw or {}, context="suite generation")
    _reject_unknown(
        data,
        allowed={"temperature", "max_output_tokens", "seed", "stop", "extra"},
        context="suite generation",
    )
    stop_raw = data.get("stop") or []
    if not isinstance(stop_raw, list):
        raise SuiteConfigError("suite generation stop must be a list")
    extra = data.get("extra") or {}
    return GenerationConfig(
        temperature=(
            float(data["temperature"]) if data.get("temperature") is not None else None
        ),
        max_output_tokens=(
            int(data["max_output_tokens"])
            if data.get("max_output_tokens") is not None
            else None
        ),
        seed=int(data["seed"]) if data.get("seed") is not None else None,
        stop=tuple(str(item) for item in stop_raw),
        extra=dict(_mapping(extra, context="suite generation extra")),
    )


def load_suite_spec(path: Path) -> BenchmarkSuiteSpec:
    payload = load_yaml_mapping(path, required=True)
    raw = _mapping(payload.get("suite"), context="suite")
    _reject_unknown(
        raw,
        allowed={
            "id",
            "suite_id",
            "version",
            "description",
            "default_profile",
            "generation",
            "capabilities",
            "options",
        },
        context="suite",
    )
    capabilities_raw = _mapping(raw.get("capabilities"), context="suite capabilities")
    options = raw.get("options") or {}
    return BenchmarkSuiteSpec(
        suite_id=str(raw.get("id") or raw.get("suite_id") or ""),
        version=str(raw.get("version") or ""),
        description=(
            str(raw["description"]) if raw.get("description") is not None else None
        ),
        default_profile=str(raw.get("default_profile") or ""),
        generation=_generation(raw.get("generation")),
        capabilities=tuple(
            _capability(
                str(capability_id),
                _mapping(value, context=f"capability {capability_id!r}"),
            )
            for capability_id, value in capabilities_raw.items()
        ),
        options=dict(_mapping(options, context="suite options")),
    )
