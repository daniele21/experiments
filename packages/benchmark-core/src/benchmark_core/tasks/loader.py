from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core.config import load_yaml_mapping
from benchmark_core.contracts import ModelCapabilities
from benchmark_core.tasks.contracts import TaskMetricSpec, TaskSpec
from benchmark_core.tasks.registry import TaskRegistryError


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TaskRegistryError(f"{context} must be a mapping")
    return value


def _reject_unknown(
    raw: Mapping[str, Any],
    *,
    allowed: set[str],
    context: str,
) -> None:
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise TaskRegistryError(
            f"{context} contains unsupported fields: {', '.join(unknown)}"
        )


def _strings(value: Any, *, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise TaskRegistryError(f"{context} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise TaskRegistryError(f"{context} must contain non-empty strings")
    return tuple(value)


def _capabilities(value: Any, *, task_id: str) -> ModelCapabilities:
    if value is None:
        return ModelCapabilities()
    raw = _mapping(value, context=f"task {task_id!r} required_capabilities")
    allowed = {
        "text_input",
        "image_input",
        "image_output",
        "image_editing",
        "multi_image_input",
    }
    _reject_unknown(
        raw,
        allowed=allowed,
        context=f"task {task_id!r} required_capabilities",
    )
    values: dict[str, bool] = {}
    for key, enabled in raw.items():
        if not isinstance(enabled, bool):
            raise TaskRegistryError(
                f"task {task_id!r} capability {key!r} must be boolean"
            )
        values[str(key)] = enabled
    return ModelCapabilities(**values)


def _metric(raw: Any, *, task_id: str, index: int) -> TaskMetricSpec:
    data = _mapping(raw, context=f"task {task_id!r} metric {index}")
    _reject_unknown(
        data,
        allowed={"name", "primary", "options"},
        context=f"task {task_id!r} metric {index}",
    )
    options = data.get("options") or {}
    return TaskMetricSpec(
        name=str(data.get("name") or ""),
        primary=bool(data.get("primary", False)),
        options=dict(_mapping(options, context=f"task {task_id!r} metric options")),
    )


def _task(task_id: str, raw: Mapping[str, Any]) -> TaskSpec:
    _reject_unknown(
        raw,
        allowed={
            "version",
            "plugin",
            "plugin_id",
            "evaluator",
            "evaluator_id",
            "evaluator_version",
            "required_capabilities",
            "compatible_datasets",
            "prompt",
            "metrics",
            "options",
        },
        context=f"task {task_id!r}",
    )

    prompt_id = None
    prompt_version = None
    if raw.get("prompt") is not None:
        prompt = _mapping(raw["prompt"], context=f"task {task_id!r} prompt")
        _reject_unknown(
            prompt,
            allowed={"id", "version"},
            context=f"task {task_id!r} prompt",
        )
        prompt_id = str(prompt.get("id") or "")
        prompt_version = str(prompt.get("version") or "")

    metrics_raw = raw.get("metrics") or []
    if not isinstance(metrics_raw, list):
        raise TaskRegistryError(f"task {task_id!r} metrics must be a list")

    options = raw.get("options") or {}
    return TaskSpec(
        task_id=task_id,
        version=str(raw.get("version") or ""),
        plugin_id=str(raw.get("plugin") or raw.get("plugin_id") or ""),
        evaluator_id=str(raw.get("evaluator") or raw.get("evaluator_id") or ""),
        evaluator_version=str(raw.get("evaluator_version") or "1"),
        required_capabilities=_capabilities(
            raw.get("required_capabilities"),
            task_id=task_id,
        ),
        compatible_datasets=_strings(
            raw.get("compatible_datasets"),
            context=f"task {task_id!r} compatible_datasets",
        ),
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        metrics=tuple(
            _metric(metric, task_id=task_id, index=index)
            for index, metric in enumerate(metrics_raw)
        ),
        options=dict(_mapping(options, context=f"task {task_id!r} options")),
    )


def load_task_specs(path: Path) -> dict[str, TaskSpec]:
    payload = load_yaml_mapping(path, required=True)
    raw_tasks = _mapping(payload.get("tasks"), context="tasks")
    if not raw_tasks:
        raise TaskRegistryError("Task catalog must define at least one task")

    return {
        str(task_id): _task(
            str(task_id),
            _mapping(raw, context=f"task {task_id!r}"),
        )
        for task_id, raw in raw_tasks.items()
    }
