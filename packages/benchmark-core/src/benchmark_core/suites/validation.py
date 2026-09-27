from __future__ import annotations

from dataclasses import dataclass

from benchmark_core.datasets import DatasetProfileSpec, DatasetRegistry
from benchmark_core.suites.contracts import BenchmarkSuiteSpec, CapabilitySpec
from benchmark_core.tasks import TaskRegistry


class SuiteValidationError(ValueError):
    """Raised when suite references are inconsistent with registries."""


@dataclass(frozen=True)
class ResolvedCapability:
    spec: CapabilitySpec
    profile: DatasetProfileSpec


def validate_suite(
    suite: BenchmarkSuiteSpec,
    *,
    tasks: TaskRegistry,
    datasets: DatasetRegistry,
    profiles: dict[str, DatasetProfileSpec],
) -> tuple[ResolvedCapability, ...]:
    try:
        profile = profiles[suite.default_profile]
    except KeyError as exc:
        raise SuiteValidationError(
            f"Suite {suite.suite_id!r} references unknown default profile "
            f"{suite.default_profile!r}"
        ) from exc

    resolved: list[ResolvedCapability] = []
    for capability in suite.capabilities:
        task = tasks.get(capability.task_id)
        declared_task_metrics = {metric.name for metric in task.spec.metrics}

        for dataset_id in capability.dataset_ids:
            datasets.get(dataset_id)
            tasks.validate_dataset(capability.task_id, dataset_id)

        for metric in capability.metrics:
            if (
                metric.source in {"task_metric", "evaluation"}
                and metric.name not in declared_task_metrics
            ):
                raise SuiteValidationError(
                    f"Capability {capability.capability_id!r} metric {metric.name!r} "
                    f"is not declared by task {capability.task_id!r}"
                )

        resolved.append(ResolvedCapability(spec=capability, profile=profile))

    return tuple(resolved)
