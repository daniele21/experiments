from model_capability_bench.tasks.classification import IntentClassificationTask
from model_capability_bench.tasks.registry import build_task_plugins, build_task_registry
from model_capability_bench.tasks.structured_output import StructuredOutputTask

__all__ = [
    "IntentClassificationTask",
    "StructuredOutputTask",
    "build_task_plugins",
    "build_task_registry",
]
