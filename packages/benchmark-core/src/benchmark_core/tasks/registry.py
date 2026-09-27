from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from benchmark_core.capabilities import validate_model_capabilities
from benchmark_core.contracts import ModelSpec
from benchmark_core.tasks.contracts import BenchmarkTask, TaskSpec

TaskFactory = Callable[[TaskSpec], BenchmarkTask]


class TaskRegistryError(ValueError):
    """Raised when task definitions or plugin registration are inconsistent."""


@dataclass
class TaskPluginRegistry:
    _factories: dict[str, TaskFactory] = field(default_factory=dict)

    def register(
        self,
        plugin_id: str,
        factory: TaskFactory,
        *,
        replace: bool = False,
    ) -> None:
        key = plugin_id.strip()
        if not key:
            raise TaskRegistryError("plugin_id must not be empty")
        if key in self._factories and not replace:
            raise TaskRegistryError(f"Task plugin already registered: {key}")
        self._factories[key] = factory

    def create(self, spec: TaskSpec) -> BenchmarkTask:
        try:
            factory = self._factories[spec.plugin_id]
        except KeyError as exc:
            raise TaskRegistryError(
                f"No task plugin registered for {spec.plugin_id!r}"
            ) from exc

        task = factory(spec)
        if not isinstance(task, BenchmarkTask):
            raise TaskRegistryError(
                f"Plugin {spec.plugin_id!r} did not create a BenchmarkTask"
            )
        if task.spec != spec:
            raise TaskRegistryError(
                f"Plugin {spec.plugin_id!r} changed the authoritative TaskSpec"
            )
        return task

    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


@dataclass(frozen=True)
class TaskRegistry:
    tasks: Mapping[str, BenchmarkTask]

    def __post_init__(self) -> None:
        for task_id, task in self.tasks.items():
            if task.spec.task_id != task_id:
                raise TaskRegistryError(
                    f"Task registry key {task_id!r} does not match "
                    f"TaskSpec {task.spec.task_id!r}"
                )

    @classmethod
    def from_specs(
        cls,
        specs: Mapping[str, TaskSpec],
        plugins: TaskPluginRegistry,
    ) -> TaskRegistry:
        tasks: dict[str, BenchmarkTask] = {}
        for task_id, spec in specs.items():
            if task_id != spec.task_id:
                raise TaskRegistryError(
                    f"Task spec key {task_id!r} does not match task_id {spec.task_id!r}"
                )
            tasks[task_id] = plugins.create(spec)
        return cls(tasks)

    def get(self, task_id: str) -> BenchmarkTask:
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            raise TaskRegistryError(f"Unknown task: {task_id}") from exc

    def select(self, task_ids: Sequence[str] | None = None) -> list[BenchmarkTask]:
        if task_ids is None:
            keys = list(self.tasks)
        else:
            keys = list(dict.fromkeys(task_ids))
        return [self.get(task_id) for task_id in keys]

    def validate_dataset(self, task_id: str, dataset_id: str) -> None:
        task = self.get(task_id)
        compatible = task.spec.compatible_datasets
        if compatible and dataset_id not in compatible:
            raise TaskRegistryError(
                f"Task {task_id!r} is not compatible with dataset {dataset_id!r}; "
                f"expected one of: {', '.join(compatible)}"
            )

    def validate_model(self, task_id: str, model: ModelSpec) -> None:
        task = self.get(task_id)
        validate_model_capabilities(model, task.spec.required_capabilities)

    def summary(self) -> dict[str, object]:
        return {
            "tasks": len(self.tasks),
            "task_ids": sorted(self.tasks),
            "plugins": sorted({task.spec.plugin_id for task in self.tasks.values()}),
        }
