from __future__ import annotations

from pathlib import Path

from benchmark_core import TaskPluginRegistry, TaskRegistry, load_task_specs

from model_capability_bench.tasks.classification import (
    CalibratedIntentClassificationTask,
    IntentClassificationTask,
)
from model_capability_bench.tasks.qa_abstention import QaAbstentionTask
from model_capability_bench.tasks.reasoning import MathematicalReasoningTask
from model_capability_bench.tasks.structured_output import StructuredOutputTask


def build_task_plugins() -> TaskPluginRegistry:
    plugins = TaskPluginRegistry()
    plugins.register("intent-classification", IntentClassificationTask)
    plugins.register(
        "calibrated-intent-classification",
        CalibratedIntentClassificationTask,
    )
    plugins.register("qa-abstention", QaAbstentionTask)
    plugins.register("mathematical-reasoning", MathematicalReasoningTask)
    plugins.register("structured-output", StructuredOutputTask)
    return plugins


def build_task_registry(catalog_path: str | Path) -> TaskRegistry:
    specs = load_task_specs(Path(catalog_path))
    return TaskRegistry.from_specs(specs, build_task_plugins())
