from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_INFERENCE_KEYS = {
    "temperature", "max_output_tokens", "seed", "stop",
    "top_p", "top_k", "min_p", "repeat_penalty",
}
_RUNTIME_KEYS = {
    "backend", "ctx_size", "max_kv_size", "n_gpu_layers", "n_threads",
    "n_batch", "n_ubatch", "offload_kqv", "flash_attn", "use_mmap",
    "timeout", "startup_timeout", "max_concurrent_requests",
    "enable_thinking", "show_thinking",
}


@dataclass(frozen=True)
class SweepSpec:
    sweep_id: str
    strategy: str
    baseline_inference: dict[str, Any]
    baseline_runtime: dict[str, Any]
    dimensions: dict[str, tuple[Any, ...]]


@dataclass(frozen=True)
class SweepPoint:
    sweep_id: str
    configuration_id: str
    label: str
    inference_config: dict[str, Any]
    runtime_config: dict[str, Any]
    changed_dimension: str | None
    is_baseline: bool


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    return dict(value)


def _validate_config(namespace: str, config: dict[str, Any]) -> None:
    allowed = _INFERENCE_KEYS if namespace == "inference" else _RUNTIME_KEYS
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise ValueError(f"Unsupported {namespace} sweep keys: {', '.join(unknown)}")

    positive_ints = {
        "max_output_tokens", "top_k", "ctx_size", "max_kv_size", "n_threads",
        "n_batch", "n_ubatch", "timeout", "startup_timeout",
        "max_concurrent_requests",
    }
    for key in positive_ints.intersection(config):
        value = config[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{namespace}.{key} must be a positive integer")

    if "temperature" in config and float(config["temperature"]) < 0:
        raise ValueError("inference.temperature must be >= 0")
    if "repeat_penalty" in config and float(config["repeat_penalty"]) <= 0:
        raise ValueError("inference.repeat_penalty must be > 0")
    for key in ("top_p", "min_p"):
        if key in config and not 0 <= float(config[key]) <= 1:
            raise ValueError(f"inference.{key} must be between 0 and 1")


def load_sweep(root: Path, sweep_id: str) -> SweepSpec:
    path = root / "sweeps.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Sweep registry not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sweeps = payload.get("sweeps") or {}
    if sweep_id not in sweeps:
        available = ", ".join(sorted(sweeps))
        raise ValueError(f"Unknown sweep {sweep_id!r}; available: {available or 'none'}")

    raw = _mapping(sweeps[sweep_id], field=f"sweeps.{sweep_id}")
    strategy = str(raw.get("strategy") or "one_at_a_time")
    if strategy not in {"one_at_a_time", "factorial"}:
        raise ValueError(f"Sweep {sweep_id!r} has unsupported strategy {strategy!r}")

    baseline = _mapping(raw.get("baseline"), field=f"{sweep_id}.baseline")
    baseline_inference = _mapping(
        baseline.get("inference"), field=f"{sweep_id}.baseline.inference"
    )
    baseline_runtime = _mapping(
        baseline.get("runtime"), field=f"{sweep_id}.baseline.runtime"
    )
    _validate_config("inference", baseline_inference)
    _validate_config("runtime", baseline_runtime)

    raw_dimensions = _mapping(raw.get("dimensions"), field=f"{sweep_id}.dimensions")
    dimensions: dict[str, tuple[Any, ...]] = {}
    for dimension, values in raw_dimensions.items():
        if "." not in dimension:
            raise ValueError(f"Sweep dimension {dimension!r} must use inference.* or runtime.*")
        namespace, key = dimension.split(".", 1)
        if namespace not in {"inference", "runtime"}:
            raise ValueError(f"Sweep dimension {dimension!r} has unsupported namespace")
        if not isinstance(values, list) or not values:
            raise ValueError(f"Sweep dimension {dimension!r} must be a non-empty list")
        for value in values:
            _validate_config(namespace, {key: value})
        dimensions[str(dimension)] = tuple(values)

    if not dimensions:
        raise ValueError(f"Sweep {sweep_id!r} has no dimensions")
    return SweepSpec(
        sweep_id=sweep_id,
        strategy=strategy,
        baseline_inference=baseline_inference,
        baseline_runtime=baseline_runtime,
        dimensions=dimensions,
    )


def _configuration_id(
    sweep_id: str,
    inference_config: dict[str, Any],
    runtime_config: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {"inference": inference_config, "runtime": runtime_config},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{sweep_id}-{digest}"


def _point(
    spec: SweepSpec,
    *,
    inference: dict[str, Any],
    runtime: dict[str, Any],
    label: str,
    changed_dimension: str | None,
    is_baseline: bool,
) -> SweepPoint:
    _validate_config("inference", inference)
    _validate_config("runtime", runtime)
    return SweepPoint(
        sweep_id=spec.sweep_id,
        configuration_id=_configuration_id(spec.sweep_id, inference, runtime),
        label=label,
        inference_config=dict(inference),
        runtime_config=dict(runtime),
        changed_dimension=changed_dimension,
        is_baseline=is_baseline,
    )


def expand_sweep(spec: SweepSpec) -> tuple[SweepPoint, ...]:
    baseline = _point(
        spec,
        inference=dict(spec.baseline_inference),
        runtime=dict(spec.baseline_runtime),
        label="baseline",
        changed_dimension=None,
        is_baseline=True,
    )
    points: list[SweepPoint] = [baseline]

    if spec.strategy == "one_at_a_time":
        for dimension, values in spec.dimensions.items():
            namespace, key = dimension.split(".", 1)
            for value in values:
                inference = dict(spec.baseline_inference)
                runtime = dict(spec.baseline_runtime)
                target = inference if namespace == "inference" else runtime
                if target.get(key) == value:
                    continue
                target[key] = value
                points.append(_point(
                    spec,
                    inference=inference,
                    runtime=runtime,
                    label=f"{dimension}={value}",
                    changed_dimension=dimension,
                    is_baseline=False,
                ))
    else:
        names = tuple(spec.dimensions)
        for values in itertools.product(*(spec.dimensions[name] for name in names)):
            inference = dict(spec.baseline_inference)
            runtime = dict(spec.baseline_runtime)
            labels: list[str] = []
            for dimension, value in zip(names, values, strict=True):
                namespace, key = dimension.split(".", 1)
                target = inference if namespace == "inference" else runtime
                target[key] = value
                labels.append(f"{dimension}={value}")
            points.append(_point(
                spec,
                inference=inference,
                runtime=runtime,
                label=", ".join(labels),
                changed_dimension="factorial",
                is_baseline=(
                    inference == spec.baseline_inference
                    and runtime == spec.baseline_runtime
                ),
            ))

    deduped: dict[str, SweepPoint] = {}
    for point in points:
        existing = deduped.get(point.configuration_id)
        if existing is None or point.is_baseline:
            deduped[point.configuration_id] = point
    return tuple(deduped.values())
