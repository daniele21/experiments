from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import (
    BenchmarkTask,
    CapabilityMismatchError,
    GenerationConfig,
    InferenceRequest,
    InferenceResult,
    MetricResult,
    ModelCapabilities,
    ModelSpec,
    Sample,
    TaskExecutionContext,
    TaskPluginRegistry,
    TaskRegistry,
    TaskRegistryError,
    TaskResult,
    TaskSpec,
    load_task_specs,
)


class _EchoTask:
    def __init__(self, spec: TaskSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> TaskSpec:
        return self._spec

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        return InferenceRequest(
            request_id=f"{context.run_id}:{sample.sample_id}",
            input=sample.input,
            generation=context.generation,
            task_metadata={
                "task_id": self.spec.task_id,
                "task_version": self.spec.version,
                "dataset_id": context.dataset_id,
            },
        )

    def evaluate(
        self,
        sample: Sample,
        inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        correct = inference.normalized_output == sample.expected
        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=inference.normalized_output,
            expected=sample.expected,
            metrics=(
                MetricResult(name="accuracy", value=float(correct), primary=True),
            ),
            valid=inference.valid,
            error=inference.error.message if inference.error is not None else None,
            metadata={"dataset_id": context.dataset_id},
        )


def _spec() -> TaskSpec:
    return TaskSpec(
        task_id="classification",
        version="1",
        plugin_id="echo-classification",
        evaluator_id="exact-match",
        evaluator_version="1",
        required_capabilities=ModelCapabilities(text_input=True),
        compatible_datasets=("dataset-a",),
        prompt_id="classification-v1",
        prompt_version="1",
    )


def test_task_plugin_registry_builds_structural_plugins() -> None:
    plugins = TaskPluginRegistry()
    plugins.register("echo-classification", _EchoTask)

    registry = TaskRegistry.from_specs({"classification": _spec()}, plugins)
    task = registry.get("classification")

    assert isinstance(task, BenchmarkTask)
    assert registry.summary() == {
        "tasks": 1,
        "task_ids": ["classification"],
        "plugins": ["echo-classification"],
    }


def test_task_request_and_evaluation_are_provider_independent() -> None:
    plugins = TaskPluginRegistry()
    plugins.register("echo-classification", _EchoTask)
    task = TaskRegistry.from_specs({"classification": _spec()}, plugins).get(
        "classification"
    )
    sample = Sample(sample_id="sample-1", input="hello", expected="greeting")
    context = TaskExecutionContext(
        run_id="run-1",
        dataset_id="dataset-a",
        profile="smoke",
        generation=GenerationConfig(temperature=0.0, seed=42),
    )

    request = task.build_request(sample, context)
    result = task.evaluate(
        sample,
        InferenceResult(
            provider_id="fake",
            model_id="fake-model",
            raw_output="greeting",
            normalized_output="greeting",
            latency_ms=1.0,
        ),
        context,
    )

    assert request.input == "hello"
    assert request.task_metadata["task_version"] == "1"
    assert request.generation.seed == 42
    assert result.metrics[0].name == "accuracy"
    assert result.metrics[0].value == 1.0


def test_task_registry_validates_dataset_and_model_capabilities() -> None:
    spec = TaskSpec(
        task_id="vision-task",
        version="1",
        plugin_id="echo-classification",
        evaluator_id="exact-match",
        required_capabilities=ModelCapabilities(
            text_input=True,
            image_input=True,
        ),
        compatible_datasets=("vision-dataset",),
    )
    plugins = TaskPluginRegistry()
    plugins.register("echo-classification", _EchoTask)
    registry = TaskRegistry.from_specs({"vision-task": spec}, plugins)

    registry.validate_dataset("vision-task", "vision-dataset")
    with pytest.raises(TaskRegistryError, match="not compatible"):
        registry.validate_dataset("vision-task", "text-dataset")

    text_model = ModelSpec(
        model_key="text-model",
        model_id="vendor/text",
        runtime_key="api",
    )
    with pytest.raises(CapabilityMismatchError, match="image_input"):
        registry.validate_model("vision-task", text_model)

    vision_model = ModelSpec(
        model_key="vision-model",
        model_id="vendor/vision",
        runtime_key="api",
        capabilities=ModelCapabilities(text_input=True, image_input=True),
    )
    registry.validate_model("vision-task", vision_model)


def test_task_catalog_loader_is_strict_and_versioned(tmp_path: Path) -> None:
    path = tmp_path / "tasks.yaml"
    path.write_text(
        """
tasks:
  classification:
    version: "2"
    plugin: echo-classification
    evaluator: exact-match
    evaluator_version: "3"
    compatible_datasets: [dataset-a]
    required_capabilities:
      text_input: true
    prompt:
      id: classification-v2
      version: "2"
    metrics:
      - name: accuracy
        primary: true
      - name: macro_f1
""".strip(),
        encoding="utf-8",
    )

    spec = load_task_specs(path)["classification"]

    assert spec.version == "2"
    assert spec.plugin_id == "echo-classification"
    assert spec.evaluator_version == "3"
    assert spec.prompt_id == "classification-v2"
    assert spec.prompt_version == "2"
    assert [metric.name for metric in spec.metrics] == ["accuracy", "macro_f1"]
    assert spec.metrics[0].primary is True


def test_task_catalog_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "tasks.yaml"
    path.write_text(
        """
tasks:
  classification:
    version: "1"
    plugin: echo-classification
    evaluator: exact-match
    evaluatr: typo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(TaskRegistryError, match="evaluatr"):
        load_task_specs(path)


def test_task_spec_requires_prompt_version_and_unique_metrics() -> None:
    with pytest.raises(ValueError, match="provided together"):
        TaskSpec(
            task_id="task",
            version="1",
            plugin_id="plugin",
            evaluator_id="eval",
            prompt_id="prompt",
        )

    with pytest.raises(ValueError, match="unique"):
        TaskSpec(
            task_id="task",
            version="1",
            plugin_id="plugin",
            evaluator_id="eval",
            metrics=(
                # Duplicate metric names are ambiguous in aggregate reporting.
                # Keep this contract fail-closed.
                __import__("benchmark_core").TaskMetricSpec(name="accuracy"),
                __import__("benchmark_core").TaskMetricSpec(name="accuracy"),
            ),
        )
