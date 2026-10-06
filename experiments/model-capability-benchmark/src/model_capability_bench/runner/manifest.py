from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import (
    load_pricing_snapshot,
    pricing_snapshot_metadata,
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
    "sweeps.yaml",
    "reporting.yaml",
    "pricing_snapshot.json",
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
    signatures = summary.metadata.get("signatures") or {}
    model_signatures = signatures.get("models") or {}
    execution_signatures = signatures.get("executions") or {}
    execution_metadata = signatures.get("execution_metadata") or {}
    benchmark_signatures = signatures.get("benchmarks") or {}
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
                "family": resolved.model.family,
                "parameters_b": resolved.model.parameters_b,
                "artifact_size_bytes": (
                    resolved.model.artifact.size_bytes
                    if (
                        resolved.model.artifact is not None
                        and resolved.model.artifact.size_bytes is not None
                    )
                    else (
                        (execution_metadata.get(model_key) or {}).get(
                            "artifact_size_bytes"
                        )
                    )
                ),
                "model_signature": model_signatures.get(model_key),
                "execution_signature": execution_signatures.get(model_key),
                "execution_metadata": execution_metadata.get(model_key),
                "artifact_format": (
                    resolved.model.artifact.format
                    if resolved.model.artifact is not None
                    else None
                ),
                "quantization": (
                    resolved.model.artifact.quantization
                    if resolved.model.artifact is not None
                    else None
                ),
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
            "benchmark_signature": benchmark_signatures.get(
                capability.spec.capability_id
            ),
            "benchmark": {
                tier_id: to_jsonable(tier)
                for tier_id, tier in capability.spec.benchmark_tiers.items()
            },
            "comparison": to_jsonable(capability.spec.comparison),
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

    pricing_path = suite.root / "pricing_snapshot.json"
    pricing = (
        pricing_snapshot_metadata(load_pricing_snapshot(pricing_path))
        if pricing_path.is_file()
        else {"semantics": "provider-reported API cost when available; unknown is null"}
    )

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
            "configuration_id": config.configuration_id,
            "inference_config": to_jsonable(config.inference_config),
            "runtime_config": to_jsonable(config.runtime_config),
        },
        pricing=pricing,
        packages=(
            "benchmark-core",
            "model-capability-bench",
            "openai",
            "jsonschema",
        ),
    )

    environment_payload = json.loads(
        (output_dir / "environment.json").read_text(encoding="utf-8")
    )

    payload = {
        "schema_version": "1",
        "git_commit": environment_payload.get("git_commit"),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "run": to_jsonable(summary),
        "suite": {
            "suite_id": suite.suite.suite_id,
            "version": suite.suite.version,
            "profile": config.profile,
            "seed": config.seed,
        },
        "models": resolved_models,
        "configuration": {
            "configuration_id": config.configuration_id,
            "experiment_kind": str(
                config.metadata.get("experiment_kind") or "standard"
            ),
            "sweep_id": config.metadata.get("sweep_id"),
            "label": config.metadata.get("sweep_label"),
            "changed_dimension": config.metadata.get("changed_dimension"),
            "is_baseline": bool(config.metadata.get("is_baseline", False)),
            "inference": to_jsonable(config.inference_config),
            "runtime": to_jsonable(config.runtime_config),
        },
        "capabilities": selected_capabilities,
        "signatures": signatures,
        "config_checksums": _config_checksums(suite.root),
        "evidence": {
            "state": "state.jsonl",
            "raw": "raw.jsonl",
            "evaluation": "evaluation.jsonl",
            "aggregates": "aggregates.jsonl",
            "report_index": "report_index.jsonl",
            "events": "events.jsonl",
            "resource_samples": "resource_samples.jsonl",
            "resource_summary": "resource_summary.jsonl",
        },
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
