from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmark_core.datasets.cache import ensure_cached_url
from benchmark_core.datasets.contracts import DatasetLoadContext, DatasetSpec


def require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{context} must be a mapping")
    return value


def require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be non-empty text")
    return value


def require_string_list(value: Any, *, context: str) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(f"{context} must contain non-empty strings")
    return tuple(str(item) for item in value)


def safe_child(base: Path, relative: str, *, context: str) -> Path:
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute():
        raise ValueError(f"{context} must be a relative path")
    base_resolved = base.resolve()
    candidate = (base_resolved / candidate_relative).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValueError(f"{context} escapes its configured base directory")
    return candidate


def cached_source(
    spec: DatasetSpec,
    context: DatasetLoadContext,
    *,
    file_key: str,
) -> Path:
    files = require_mapping(
        spec.options.get("files"),
        context=f"dataset {spec.dataset_id!r} files",
    )
    entry = require_mapping(
        files.get(file_key),
        context=f"dataset {spec.dataset_id!r} file {file_key!r}",
    )
    url = require_text(
        entry.get("url"),
        context=f"dataset {spec.dataset_id!r} file {file_key!r} url",
    )
    cache_path = require_text(
        entry.get("cache_path"),
        context=f"dataset {spec.dataset_id!r} file {file_key!r} cache_path",
    )
    timeout = spec.options.get("timeout_seconds")
    user_agent = spec.options.get("user_agent")
    if not isinstance(timeout, int | float) or timeout <= 0:
        raise ValueError(
            f"dataset {spec.dataset_id!r} timeout_seconds must be positive"
        )
    user_agent_text = require_text(
        user_agent,
        context=f"dataset {spec.dataset_id!r} user_agent",
    )
    target = safe_child(
        context.cache_dir,
        cache_path,
        context=f"dataset {spec.dataset_id!r} cache_path",
    )
    return ensure_cached_url(
        url=url,
        target=target,
        timeout_seconds=float(timeout),
        user_agent=user_agent_text,
    )


def single_cached_source(
    spec: DatasetSpec,
    context: DatasetLoadContext,
) -> Path:
    entry = require_mapping(
        spec.options.get("file"),
        context=f"dataset {spec.dataset_id!r} file",
    )
    synthetic_options = dict(spec.options)
    synthetic_options["files"] = {"source": dict(entry)}
    synthetic = DatasetSpec(
        dataset_id=spec.dataset_id,
        version=spec.version,
        adapter_id=spec.adapter_id,
        source=spec.source,
        revision=spec.revision,
        split=spec.split,
        license_id=spec.license_id,
        sample_schema_version=spec.sample_schema_version,
        cache_mode=spec.cache_mode,
        options=synthetic_options,
    )
    return cached_source(synthetic, context, file_key="source")
