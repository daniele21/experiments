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

        unknown_tiers = set(capability.benchmark_tiers) - set(profiles)
        if unknown_tiers:
            raise SuiteValidationError(
                f"Capability {capability.capability_id!r} declares benchmark tiers "
                "without matching profiles: " + ", ".join(sorted(unknown_tiers))
            )

        if (
            capability.comparison.metric is not None
            and capability.comparison.metric not in declared_task_metrics
        ):
            raise SuiteValidationError(
                f"Capability {capability.capability_id!r} comparison metric "
                f"{capability.comparison.metric!r} is not declared by task "
                f"{capability.task_id!r}"
            )

        for dataset_id in capability.dataset_ids:
            datasets.get(dataset_id)
            tasks.validate_dataset(capability.task_id, dataset_id)

        for binding in capability.context_bindings:
            if (
                binding.source == "dataset_metadata"
                and binding.dataset_id not in capability.dataset_ids
            ):
                raise SuiteValidationError(
                    f"Capability {capability.capability_id!r} context "
                    f"{binding.key!r} references dataset {binding.dataset_id!r} "
                    "outside the capability dataset set"
                )

        for metric in capability.metrics:
            task_metric_name = metric.field or metric.name
            if (
                metric.source == "task_metric"
                and task_metric_name not in declared_task_metrics
            ):
                raise SuiteValidationError(
                    f"Capability {capability.capability_id!r} task metric "
                    f"{task_metric_name!r} is not declared by task "
                    f"{capability.task_id!r}"
                )

        resolved.append(ResolvedCapability(spec=capability, profile=profile))

    return tuple(resolved)
