from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from benchmark_core import DatasetLoadContext, DatasetLoadResult, DatasetProfileSpec

from model_capability_bench.suite import CapabilitySuiteBundle


class CapabilityDatasetLoadError(RuntimeError):
    def __init__(self, dataset_id: str, cause: Exception) -> None:
        super().__init__(str(cause))
        self.dataset_id = dataset_id
        self.__cause__ = cause


def selection_payload(capability, profile_id: str) -> dict[str, Any]:
    tier = capability.spec.benchmark_tier(profile_id)
    if tier is None:
        return {}
    return {
        "strategy": tier.selection.strategy,
        "quotas": [
            {"match": dict(quota.match), "count": quota.count}
            for quota in tier.selection.quotas
        ],
    }


def load_capability_datasets(
    *,
    suite: CapabilitySuiteBundle,
    capability,
    profile: DatasetProfileSpec,
    profile_id: str,
    cache_dir: Path,
    seed: int,
    cache: MutableMapping[tuple[str, str, str, int], DatasetLoadResult],
) -> dict[str, DatasetLoadResult]:
    tier = capability.spec.benchmark_tier(profile_id)
    selection = selection_payload(capability, profile_id)
    loaded: dict[str, DatasetLoadResult] = {}

    for dataset_id in capability.spec.dataset_ids:
        fallback_limit = profile.max_cases_for(dataset_id)
        max_cases = (
            tier.max_cases_for(dataset_id, fallback=fallback_limit)
            if tier is not None
            else fallback_limit
        )
        cache_key = (
            dataset_id,
            capability.spec.capability_id,
            profile_id,
            seed,
        )
        try:
            if cache_key not in cache:
                cache[cache_key] = suite.datasets.load(
                    dataset_id,
                    DatasetLoadContext(
                        cache_dir=cache_dir,
                        profile=profile,
                        seed=seed,
                        max_cases_override=max_cases,
                        selection=selection,
                        max_cases_override_enabled=True,
                        metadata={
                            "capability_id": capability.spec.capability_id,
                            "benchmark_tier": profile_id,
                        },
                    ),
                )
            loaded[dataset_id] = cache[cache_key]
        except Exception as exc:  # noqa: BLE001 - dataset plugin boundary
            raise CapabilityDatasetLoadError(dataset_id, exc) from exc
    return loaded
