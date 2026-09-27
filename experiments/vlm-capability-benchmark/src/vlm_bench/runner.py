from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from benchmark_core import (
    BenchmarkArm,
    append_csv_records,
    create_run_identity,
    execute_arm,
    write_environment_manifest,
)

from vlm_bench.config import ResolvedVLMModel
from vlm_bench.planning import VLMRunPlan
from vlm_bench.provider_factory import create_vlm_provider
from vlm_bench.tasks import build_ui_grounding_request, evaluate_ui_grounding

ProviderFactory = Callable[[ResolvedVLMModel, Mapping[str, str]], Any]


def _default_provider_factory(
    model: ResolvedVLMModel,
    environ: Mapping[str, str],
) -> Any:
    return create_vlm_provider(model, environ=environ)


def _metric_value(task_result: Any, name: str) -> Any:
    for metric in task_result.metrics:
        if metric.name == name:
            return metric.value
    return None


def execute_run_plan(
    plan: VLMRunPlan,
    *,
    output_dir: Path,
    environ: Mapping[str, str],
    provider_factory: ProviderFactory = _default_provider_factory,
) -> list[dict[str, Any]]:
    identity = create_run_identity(
        run_group=f"{plan.suite_id}-{plan.profile_id}",
        suite=plan.suite_id,
        runner_location="experiments/vlm-capability-benchmark",
    )
    run_dir = output_dir / identity.run_id
    evidence_path = run_dir / "evidence.csv"
    rows: list[dict[str, Any]] = []
    resolved_models: dict[str, list[str]] = {}

    for model in plan.models:
        provider = provider_factory(model, environ)
        resolved_models.setdefault(model.provider_key, []).append(model.model_id)

        for case in plan.cases:
            request = build_ui_grounding_request(
                case,
                prompt_template=plan.prompt_template,
            )
            arm = BenchmarkArm(
                model_key=model.model_key,
                task_id=plan.task_id,
                metadata={"sample_id": case.sample_id},
            )
            execution = execute_arm(
                arm,
                lambda provider=provider, request=request: provider.generate(request),
            )

            if execution.succeeded and execution.value is not None:
                inference = execution.value
                task_result = (
                    evaluate_ui_grounding(case, inference.normalized_output)
                    if inference.valid
                    else None
                )
                row = {
                    "run_id": identity.run_id,
                    "model_key": model.model_key,
                    "model_id": inference.model_id,
                    "provider_id": inference.provider_id,
                    "task_id": plan.task_id,
                    "sample_id": case.sample_id,
                    "question": case.question,
                    "prediction": json.dumps(
                        task_result.prediction if task_result else inference.normalized_output,
                        sort_keys=True,
                    ),
                    "valid": bool(inference.valid and task_result and task_result.valid),
                    "click_hit": (
                        _metric_value(task_result, "click_hit")
                        if task_result is not None
                        else None
                    ),
                    "target_match": (
                        _metric_value(task_result, "target_match")
                        if task_result is not None
                        else None
                    ),
                    "point_distance": (
                        _metric_value(task_result, "point_distance")
                        if task_result is not None
                        else None
                    ),
                    "latency_ms": inference.latency_ms,
                    "error_kind": inference.error.kind if inference.error else "",
                    "error_message": (
                        inference.error.message
                        if inference.error
                        else (task_result.error if task_result else "")
                    ),
                }
            else:
                row = {
                    "run_id": identity.run_id,
                    "model_key": model.model_key,
                    "model_id": model.model_id,
                    "provider_id": model.provider_key,
                    "task_id": plan.task_id,
                    "sample_id": case.sample_id,
                    "question": case.question,
                    "prediction": "",
                    "valid": False,
                    "click_hit": None,
                    "target_match": None,
                    "point_distance": None,
                    "latency_ms": execution.elapsed_s * 1000,
                    "error_kind": execution.error_type or "runner",
                    "error_message": execution.error_message or "",
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
            "task_id": plan.task_id,
            "evaluator_id": plan.evaluator_id,
            "sample_ids": [case.sample_id for case in plan.cases],
            "prompt_path": str(plan.prompt_path),
            "prompt_sha256": plan.prompt_sha256,
        },
        pricing={},
    )
    return rows
