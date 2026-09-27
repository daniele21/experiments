from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import (
    BenchmarkSuiteSpec,
    CapabilityContextBinding,
    CapabilityContextError,
    CapabilityMetricSpec,
    CapabilitySpec,
    DatasetLoadResult,
    DatasetSpec,
    GenerationConfig,
    Sample,
    SuiteConfigError,
    fingerprint_values,
    load_suite_spec,
    resolve_capability_context,
)


def test_suite_contract_requires_one_primary_metric() -> None:
    with pytest.raises(ValueError, match="exactly one primary"):
        CapabilitySpec(
            capability_id="classification",
            task_id="task",
            dataset_ids=("dataset",),
            metrics=(
                CapabilityMetricSpec(
                    name="accuracy",
                    source="task_metric",
                    reducer="mean",
                ),
            ),
        )


def test_suite_metric_contract_rejects_unknown_source_and_reducer() -> None:
    with pytest.raises(ValueError, match="Unsupported metric source"):
        CapabilityMetricSpec(
            name="metric",
            source="unknown",
            reducer="mean",
            primary=True,
        )

    with pytest.raises(ValueError, match="Unsupported metric reducer"):
        CapabilityMetricSpec(
            name="metric",
            source="task_metric",
            reducer="mystery",
            primary=True,
        )


def test_suite_loader_is_strict_and_loads_context_bindings(tmp_path: Path) -> None:
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
suite:
  id: core
  version: "1"
  default_profile: smoke
  generation:
    temperature: 0
    seed: 42
  capabilities:
    calibrated:
      task: calibrated-task
      datasets: [in-scope, oos]
      context:
        labels:
          source: dataset_metadata
          dataset: in-scope
          field: labels
          append: [other]
      metrics:
        - name: oos_detection
          source: evaluation
          reducer: oos_detection
          primary: true
""".strip(),
        encoding="utf-8",
    )

    suite = load_suite_spec(path)

    assert suite.suite_id == "core"
    assert suite.generation.seed == 42
    capability = suite.capabilities[0]
    assert capability.context_bindings == (
        CapabilityContextBinding(
            key="labels",
            source="dataset_metadata",
            dataset_id="in-scope",
            field="labels",
            append=("other",),
        ),
    )

    path.write_text(
        """
suite:
  id: core
  version: "1"
  default_profile: smoke
  typo: true
  capabilities: {}
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(SuiteConfigError, match="typo"):
        load_suite_spec(path)


def test_capability_context_resolves_dataset_metadata() -> None:
    spec = DatasetSpec(
        dataset_id="banking77",
        version="1",
        adapter_id="fixture",
        source="fixture",
        revision="v1",
        split="test",
    )
    samples = (Sample(sample_id="sample-1", input="text", expected="a"),)
    loaded = DatasetLoadResult(
        spec=spec,
        samples=samples,
        selection_fingerprint=fingerprint_values(["sample-1"]),
        available_count=1,
        metadata={"labels": ("a", "b")},
    )
    capability = CapabilitySpec(
        capability_id="calibration",
        task_id="task",
        dataset_ids=("banking77",),
        metrics=(
            CapabilityMetricSpec(
                name="accuracy",
                source="task_metric",
                reducer="mean",
                primary=True,
            ),
        ),
        context_bindings=(
            CapabilityContextBinding(
                key="labels",
                source="dataset_metadata",
                dataset_id="banking77",
                field="labels",
                append=("other",),
            ),
        ),
    )

    assert resolve_capability_context(
        capability,
        {"banking77": loaded},
    ) == {"labels": ("a", "b", "other")}

    with pytest.raises(CapabilityContextError, match="unloaded dataset"):
        resolve_capability_context(capability, {})


def test_suite_spec_accepts_five_independent_capabilities() -> None:
    metrics = (
        CapabilityMetricSpec(
            name="quality",
            source="task_metric",
            reducer="mean",
            primary=True,
        ),
    )
    suite = BenchmarkSuiteSpec(
        suite_id="capability-core",
        version="1",
        default_profile="smoke",
        generation=GenerationConfig(seed=42),
        capabilities=tuple(
            CapabilitySpec(
                capability_id=f"capability-{index}",
                task_id=f"task-{index}",
                dataset_ids=(f"dataset-{index}",),
                metrics=metrics,
            )
            for index in range(5)
        ),
    )

    assert len(suite.capabilities) == 5
