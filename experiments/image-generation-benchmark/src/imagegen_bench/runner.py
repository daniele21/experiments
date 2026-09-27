from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from benchmark_core import (
    ArtifactStore,
    BenchmarkArm,
    InferenceRequest,
    append_csv_records,
    create_run_identity,
    execute_arm,
    write_environment_manifest,
)

from imagegen_bench.config import ResolvedImageModel
from imagegen_bench.planning import ImageRunPlan
from imagegen_bench.provider_factory import create_image_provider


ProviderFactory = Callable[
    [ResolvedImageModel, ArtifactStore, Mapping[str, str]],
    Any,
]


def _default_provider_factory(
    model: ResolvedImageModel,
    store: ArtifactStore,
    environ: Mapping[str, str],
) -> Any:
    return create_image_provider(model, artifact_store=store, environ=environ)


def execute_run_plan(
    plan: ImageRunPlan,
    *,
    output_dir: Path,
    environ: Mapping[str, str],
    provider_factory: ProviderFactory = _default_provider_factory,
) -> list[dict[str, Any]]:
    identity = create_run_identity(
        run_group=f"{plan.suite_id}-{plan.profile_id}",
        suite=plan.suite_id,
        runner_location="experiments/image-generation-benchmark",
    )
    run_dir = output_dir / identity.run_id
    evidence_path = run_dir / "evidence.csv"
    rows: list[dict[str, Any]] = []

    resolved_models: dict[str, list[str]] = {}
    for model in plan.models:
        store = ArtifactStore(run_dir / "artifacts" / model.model_key)
        provider = provider_factory(model, store, environ)
        resolved_models.setdefault(model.provider_key, []).append(model.model_id)

        for prompt in plan.prompts:
            arm = BenchmarkArm(
                model_key=model.model_key,
                task_id=prompt.category,
                metadata={"prompt_id": prompt.prompt_id},
            )
            execution = execute_arm(
                arm,
                lambda prompt=prompt, provider=provider: provider.generate(
                    InferenceRequest(
                        request_id=f"{model.model_key}-{prompt.prompt_id}",
                        input=prompt.prompt,
                    )
                ),
            )

            if execution.succeeded and execution.value is not None:
                result = execution.value
                artifact = result.output_artifacts[0] if result.output_artifacts else None
                row = {
                    "run_id": identity.run_id,
                    "model_key": model.model_key,
                    "model_id": result.model_id,
                    "provider_id": result.provider_id,
                    "prompt_id": prompt.prompt_id,
                    "category": prompt.category,
                    "prompt": prompt.prompt,
                    "valid": result.valid,
                    "latency_ms": result.latency_ms,
                    "artifact_id": artifact.artifact_id if artifact else "",
                    "artifact_path": artifact.path if artifact else "",
                    "artifact_sha256": artifact.sha256 if artifact else "",
                    "error_kind": result.error.kind if result.error else "",
                    "error_message": result.error.message if result.error else "",
                    "generation_config": json.dumps(
                        dict(model.generation),
                        sort_keys=True,
                    ),
                }
            else:
                row = {
                    "run_id": identity.run_id,
                    "model_key": model.model_key,
                    "model_id": model.model_id,
                    "provider_id": model.provider_key,
                    "prompt_id": prompt.prompt_id,
                    "category": prompt.category,
                    "prompt": prompt.prompt,
                    "valid": False,
                    "latency_ms": execution.elapsed_s * 1000,
                    "artifact_id": "",
                    "artifact_path": "",
                    "artifact_sha256": "",
                    "error_kind": execution.error_type or "runner",
                    "error_message": execution.error_message or "",
                    "generation_config": json.dumps(
                        dict(model.generation),
                        sort_keys=True,
                    ),
                }
            rows.append(row)
            append_csv_records([row], evidence_path)

    write_environment_manifest(
        run_dir / "manifest.json",
        run_group=identity.run_group,
        suite=plan.suite_id,
        runner_location=identity.runner_location,
        requested_models={"model_keys": [model.model_key for model in plan.models]},
        resolved_models=resolved_models,
        parameters={
            "profile": plan.profile_id,
            "seed": plan.seed,
            "prompt_ids": [prompt.prompt_id for prompt in plan.prompts],
            "model_generation": {
                model.model_key: dict(model.generation)
                for model in plan.models
            },
            "benchmark_mapping": {
                model.model_key: dict(model.benchmark_mapping)
                for model in plan.models
            },
        },
        pricing={},
        packages=("openai", "google-genai"),
    )
    return rows
