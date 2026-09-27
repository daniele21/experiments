from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from benchmark_core.datasets.contracts import (
    BenchmarkDataset,
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetSpec,
)

DatasetFactory = Callable[[DatasetSpec], BenchmarkDataset]


class DatasetRegistryError(ValueError):
    """Raised when dataset definitions or plugins are inconsistent."""


@dataclass
class DatasetPluginRegistry:
    _factories: dict[str, DatasetFactory] = field(default_factory=dict)

    def register(
        self,
        adapter_id: str,
        factory: DatasetFactory,
        *,
        replace: bool = False,
    ) -> None:
        key = adapter_id.strip()
        if not key:
            raise DatasetRegistryError("adapter_id must not be empty")
        if key in self._factories and not replace:
            raise DatasetRegistryError(f"Dataset adapter already registered: {key}")
        self._factories[key] = factory

    def create(self, spec: DatasetSpec) -> BenchmarkDataset:
        try:
            factory = self._factories[spec.adapter_id]
        except KeyError as exc:
            raise DatasetRegistryError(
                f"No dataset adapter registered for {spec.adapter_id!r}"
            ) from exc

        dataset = factory(spec)
        if not isinstance(dataset, BenchmarkDataset):
            raise DatasetRegistryError(
                f"Adapter {spec.adapter_id!r} did not create a BenchmarkDataset"
            )
        if dataset.spec != spec:
            raise DatasetRegistryError(
                f"Adapter {spec.adapter_id!r} changed the authoritative DatasetSpec"
            )
        return dataset

    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


@dataclass(frozen=True)
class DatasetRegistry:
    datasets: Mapping[str, BenchmarkDataset]

    def __post_init__(self) -> None:
        for dataset_id, dataset in self.datasets.items():
            if dataset.spec.dataset_id != dataset_id:
                raise DatasetRegistryError(
                    f"Dataset registry key {dataset_id!r} does not match "
                    f"DatasetSpec {dataset.spec.dataset_id!r}"
                )

    @classmethod
    def from_specs(
        cls,
        specs: Mapping[str, DatasetSpec],
        plugins: DatasetPluginRegistry,
    ) -> DatasetRegistry:
        datasets: dict[str, BenchmarkDataset] = {}
        for dataset_id, spec in specs.items():
            if dataset_id != spec.dataset_id:
                raise DatasetRegistryError(
                    f"Dataset spec key {dataset_id!r} does not match "
                    f"dataset_id {spec.dataset_id!r}"
                )
            datasets[dataset_id] = plugins.create(spec)
        return cls(datasets)

    def get(self, dataset_id: str) -> BenchmarkDataset:
        try:
            return self.datasets[dataset_id]
        except KeyError as exc:
            raise DatasetRegistryError(f"Unknown dataset: {dataset_id}") from exc

    def select(
        self,
        dataset_ids: Sequence[str] | None = None,
    ) -> list[BenchmarkDataset]:
        if dataset_ids is None:
            keys = list(self.datasets)
        else:
            keys = list(dict.fromkeys(dataset_ids))
        return [self.get(dataset_id) for dataset_id in keys]

    def load(
        self,
        dataset_id: str,
        context: DatasetLoadContext,
    ) -> DatasetLoadResult:
        return self.get(dataset_id).load(context)

    def summary(self) -> dict[str, object]:
        return {
            "datasets": len(self.datasets),
            "dataset_ids": sorted(self.datasets),
            "adapters": sorted(
                {dataset.spec.adapter_id for dataset in self.datasets.values()}
            ),
        }
