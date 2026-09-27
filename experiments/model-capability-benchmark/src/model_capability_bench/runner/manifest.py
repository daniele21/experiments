from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import (
    sha256_file,
    to_jsonable,
    write_environment_manifest,
)

from model_capability_bench.runner.contracts import RunnerConfig, RunnerSummary
from model_capability_bench.suite import CapabilitySuiteBundle

CONFIG_FILES = (
    "models.yaml",
    "tasks.yaml",
    "datasets.yaml",
    "profiles.yaml",
    "suite.yaml",
    "runner.yaml",
)


def _config_checksums(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for name in CONFIG_FILES:
        path = root / name
        if path.is_file():
            checksums[name] = sha256_file(path)
    return checksums


def write_run_artifacts(
    *,
    suite: CapabilitySuiteBundle,
    config: RunnerConfig,
    summary: RunnerSummary,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped_models: dict[str, list[str]] = defaultdict(list)
    resolved_models: list[dict[str, Any]] = []
    for model_key in config.model_keys:
        resolved = suite.models.resolve(model_key)
        grouped_models[resolved.provider.provider_key].append(model_key)
        resolved_models.append(
            {
                "model_key": model_key,
                "model_id": resolved.model.model_id,
                "effective_model_id": resolved.effective_model_id,
                "runtime_key": resolved.runtime.runtime_key,
                "provider_key": resolved.provider.provider_key,
                "deployment": resolved.runtime.deployment,
                "lifecycle": resolved.runtime.lifecycle,
            }
        )

    selected_capability_ids = (
        config.capability_ids
        if config.capability_ids is not None
        else tuple(
            capability.spec.capability_id
            for capability in suite.resolved_capabilities
        )
    )
    selected_capabilities = [
        {
            "capability_id": capability.spec.capability_id,
            "task_id": capability.spec.task_id,
            "dataset_ids": list(capability.spec.dataset_ids),
            "metrics": [
                {
                    "name": metric.name,
                    "source": metric.source,
                    "reducer": metric.reducer,
                    "field": metric.field,
                    "primary": metric.primary,
                }
                for metric in capability.spec.metrics
            ],
        }
        for capability in suite.resolved_capabilities
        if capability.spec.capability_id in set(selected_capability_ids)
    ]

    write_environment_manifest(
        output_dir / "environment.json",
        run_group=config.run_group,
        suite=suite.suite.suite_id,
        runner_location="model-capability-benchmark",
        requested_models={
            "model_keys": list(config.model_keys),
            "capability_ids": list(selected_capability_ids),
        },
        resolved_models=grouped_models,
        parameters={
            "run_id": summary.run_id,
            "profile": config.profile,
            "seed": config.seed,
            "resume": config.resume,
            "retry_failures": config.retry_failures,
            "generation": to_jsonable(suite.suite.generation),
        },
        pricing={
            "semantics": "provider-reported API cost when available; unknown is null",
        },
        packages=(
            "benchmark-core",
            "model-capability-bench",
            "openai",
            "jsonschema",
        ),
    )

    payload = {
        "schema_version": "1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "run": to_jsonable(summary),
        "suite": {
            "suite_id": suite.suite.suite_id,
            "version": suite.suite.version,
            "profile": config.profile,
            "seed": config.seed,
        },
        "models": resolved_models,
        "capabilities": selected_capabilities,
        "config_checksums": _config_checksums(suite.root),
        "evidence": {
            "state": "state.jsonl",
            "raw": "raw.jsonl",
            "evaluation": "evaluation.jsonl",
            "aggregates": "aggregates.jsonl",
            "events": "events.jsonl",
        },
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
