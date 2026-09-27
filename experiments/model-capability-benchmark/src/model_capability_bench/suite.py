from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from benchmark_core import (
    BenchmarkSuiteSpec,
    DatasetProfileSpec,
    DatasetRegistry,
    RegistryBundle,
    ResolvedCapability,
    TaskRegistry,
    load_dataset_profiles,
    load_registry,
    load_suite_spec,
    validate_suite,
)

from model_capability_bench.datasets import build_dataset_registry
from model_capability_bench.tasks import build_task_registry


@dataclass(frozen=True)
class CapabilityMatrixArm:
    model_key: str
    capability_id: str
    task_id: str
    dataset_id: str
    runtime_key: str
    provider_key: str


@dataclass(frozen=True)
class CapabilitySuiteBundle:
    root: Path
    suite: BenchmarkSuiteSpec
    resolved_capabilities: tuple[ResolvedCapability, ...]
    models: RegistryBundle
    tasks: TaskRegistry
    datasets: DatasetRegistry
    profiles: Mapping[str, DatasetProfileSpec]

    def plan_matrix(
        self,
        *,
        model_keys: Sequence[str] | None = None,
        capability_ids: Sequence[str] | None = None,
    ) -> tuple[CapabilityMatrixArm, ...]:
        models = self.models.select(model_keys=model_keys)
        selected_capabilities = (
            self.resolved_capabilities
            if capability_ids is None
            else tuple(
                capability
                for capability in self.resolved_capabilities
                if capability.spec.capability_id in set(capability_ids)
            )
        )
        if capability_ids is not None:
            requested = list(dict.fromkeys(capability_ids))
            found = {item.spec.capability_id for item in selected_capabilities}
            missing = [capability_id for capability_id in requested if capability_id not in found]
            if missing:
                raise ValueError(
                    "Unknown capability IDs: " + ", ".join(missing)
                )

        arms: list[CapabilityMatrixArm] = []
        for model in models:
            for capability in selected_capabilities:
                self.tasks.validate_model(capability.spec.task_id, model.model)
                for dataset_id in capability.spec.dataset_ids:
                    arms.append(
                        CapabilityMatrixArm(
                            model_key=model.model.model_key,
                            capability_id=capability.spec.capability_id,
                            task_id=capability.spec.task_id,
                            dataset_id=dataset_id,
                            runtime_key=model.runtime.runtime_key,
                            provider_key=model.provider.provider_key,
                        )
                    )
        return tuple(arms)


def load_capability_suite(root: str | Path) -> CapabilitySuiteBundle:
    root_path = Path(root)
    models = load_registry(root_path / "models.yaml")
    tasks = build_task_registry(root_path / "tasks.yaml")
    datasets = build_dataset_registry(root_path / "datasets.yaml")
    profiles = load_dataset_profiles(root_path / "profiles.yaml")
    suite = load_suite_spec(root_path / "suite.yaml")
    resolved = validate_suite(
        suite,
        tasks=tasks,
        datasets=datasets,
        profiles=profiles,
    )
    return CapabilitySuiteBundle(
        root=root_path,
        suite=suite,
        resolved_capabilities=resolved,
        models=models,
        tasks=tasks,
        datasets=datasets,
        profiles=profiles,
    )
