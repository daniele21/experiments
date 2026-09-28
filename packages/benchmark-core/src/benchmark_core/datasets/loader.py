from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core.config import load_yaml_mapping
from benchmark_core.datasets.contracts import DatasetProfileSpec, DatasetSpec
from benchmark_core.datasets.registry import DatasetRegistryError


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DatasetRegistryError(f"{context} must be a mapping")
    return value


def _reject_unknown(
    raw: Mapping[str, Any],
    *,
    allowed: set[str],
    context: str,
) -> None:
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise DatasetRegistryError(
            f"{context} contains unsupported fields: {', '.join(unknown)}"
        )


def _options(value: Any, *, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    return {str(key): item for key, item in _mapping(value, context=context).items()}


def _dataset(dataset_id: str, raw: Mapping[str, Any]) -> DatasetSpec:
    _reject_unknown(
        raw,
        allowed={
            "version",
            "adapter",
            "adapter_id",
            "source",
            "revision",
            "split",
            "license",
            "license_id",
            "sample_schema_version",
            "cache_mode",
            "options",
        },
        context=f"dataset {dataset_id!r}",
    )
    return DatasetSpec(
        dataset_id=dataset_id,
        version=str(raw.get("version") or ""),
        adapter_id=str(raw.get("adapter") or raw.get("adapter_id") or ""),
        source=str(raw.get("source") or ""),
        revision=str(raw.get("revision") or ""),
        split=str(raw.get("split") or ""),
        license_id=(
            str(raw.get("license") or raw.get("license_id"))
            if raw.get("license") is not None or raw.get("license_id") is not None
            else None
        ),
        sample_schema_version=str(raw.get("sample_schema_version") or "1"),
        cache_mode=str(raw.get("cache_mode") or "none"),
        options=_options(raw.get("options"), context=f"dataset {dataset_id!r} options"),
    )


def load_dataset_specs(path: Path) -> dict[str, DatasetSpec]:
    payload = load_yaml_mapping(path, required=True)
    raw_datasets = _mapping(payload.get("datasets"), context="datasets")
    if not raw_datasets:
        raise DatasetRegistryError("Dataset catalog must define at least one dataset")
    return {
        str(dataset_id): _dataset(
            str(dataset_id),
            _mapping(raw, context=f"dataset {dataset_id!r}"),
        )
        for dataset_id, raw in raw_datasets.items()
    }


def _profile(profile_id: str, raw: Mapping[str, Any]) -> DatasetProfileSpec:
    _reject_unknown(
        raw,
        allowed={"max_cases", "datasets", "options"},
        context=f"profile {profile_id!r}",
    )
    max_cases_raw = raw.get("max_cases")
    default_max_cases = int(max_cases_raw) if max_cases_raw is not None else None

    datasets_raw = raw.get("datasets") or {}
    datasets = _mapping(datasets_raw, context=f"profile {profile_id!r} datasets")
    dataset_max_cases: dict[str, int | None] = {}
    for dataset_id, value in datasets.items():
        dataset_max_cases[str(dataset_id)] = int(value) if value is not None else None

    return DatasetProfileSpec(
        profile_id=profile_id,
        default_max_cases=default_max_cases,
        dataset_max_cases=dataset_max_cases,
        options=_options(raw.get("options"), context=f"profile {profile_id!r} options"),
    )


def load_dataset_profiles(path: Path) -> dict[str, DatasetProfileSpec]:
    payload = load_yaml_mapping(path, required=True)
    raw_profiles = _mapping(payload.get("profiles"), context="profiles")
    if not raw_profiles:
        raise DatasetRegistryError("Profile catalog must define at least one profile")
    return {
        str(profile_id): _profile(
            str(profile_id),
            _mapping(raw, context=f"profile {profile_id!r}"),
        )
        for profile_id, raw in raw_profiles.items()
    }
