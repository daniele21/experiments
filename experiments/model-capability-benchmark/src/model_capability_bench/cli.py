from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from benchmark_core import parse_csv_selection, preflight_models, to_jsonable

from model_capability_bench.runner import CapabilityRunner, EvidenceStore, RunnerConfig
from model_capability_bench.runner.config import load_runner_defaults
from model_capability_bench.runner.manifest import write_run_artifacts
from model_capability_bench.runtimes import RegistryRuntimeResolver
from model_capability_bench.suite import load_capability_suite

ROOT = Path(__file__).resolve().parents[2]


def _json(value: Any) -> None:
    print(json.dumps(to_jsonable(value), indent=2, sort_keys=True))


def _selection(value: str, available: list[str]) -> tuple[str, ...]:
    return tuple(parse_csv_selection(value, available=available))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model-bench",
        description="Unified model capability benchmark runner.",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Execute a model × capability benchmark matrix.")
    run.add_argument("--models", default="all")
    run.add_argument("--capabilities", default="all")
    run.add_argument("--profile")
    run.add_argument("--seed", type=int)
    run.add_argument("--run-group", required=True)
    run.add_argument("--run-id")
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--cache-dir", type=Path)
    run.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run.add_argument(
        "--retry-failures",
        action=argparse.BooleanOptionalAction,
        default=None,
    )

    validate = sub.add_parser(
        "validate-config",
        help="Validate suite composition and provider environment.",
    )
    validate.add_argument("--models", default="all")

    sub.add_parser("models", help="List configured models.")
    sub.add_parser("tasks", help="List configured tasks.")
    sub.add_parser("datasets", help="List configured datasets.")
    sub.add_parser("capabilities", help="List configured capabilities.")
    return parser


def _catalog_payload(bundle, command: str) -> Any:
    if command == "models":
        return [
            {
                "model_key": resolved.model.model_key,
                "model_id": resolved.model.model_id,
                "effective_model_id": resolved.effective_model_id,
                "runtime_key": resolved.runtime.runtime_key,
                "provider_key": resolved.provider.provider_key,
                "deployment": resolved.runtime.deployment,
                "tags": list(resolved.model.tags),
            }
            for resolved in bundle.models.select()
        ]
    if command == "tasks":
        return [
            {
                "task_id": task.spec.task_id,
                "version": task.spec.version,
                "evaluator": task.spec.evaluator_id,
                "evaluator_version": task.spec.evaluator_version,
                "datasets": list(task.spec.compatible_datasets),
            }
            for task in bundle.tasks.select()
        ]
    if command == "datasets":
        return [
            {
                "dataset_id": dataset.spec.dataset_id,
                "version": dataset.spec.version,
                "adapter": dataset.spec.adapter_id,
                "revision": dataset.spec.revision,
                "split": dataset.spec.split,
            }
            for dataset in bundle.datasets.select()
        ]
    return [
        {
            "capability_id": item.spec.capability_id,
            "task_id": item.spec.task_id,
            "dataset_ids": list(item.spec.dataset_ids),
            "primary_metric": next(
                metric.name for metric in item.spec.metrics if metric.primary
            ),
        }
        for item in bundle.resolved_capabilities
    ]


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    bundle = load_capability_suite(root)
    defaults = load_runner_defaults(root)

    if args.command in {"models", "tasks", "datasets", "capabilities"}:
        _json(_catalog_payload(bundle, args.command))
        return 0

    available_models = list(bundle.models.models)
    model_keys = _selection(args.models, available_models)

    if args.command == "validate-config":
        models = bundle.models.select(model_keys=model_keys)
        result = preflight_models(bundle.models, models, os.environ)
        _json(
            {
                "ok": result.ok,
                "models": list(model_keys),
                "issues": list(result.issues),
                "suite_id": bundle.suite.suite_id,
                "suite_version": bundle.suite.version,
            }
        )
        return 0 if result.ok else 2

    capability_ids = _selection(
        args.capabilities,
        [
            capability.spec.capability_id
            for capability in bundle.resolved_capabilities
        ],
    )
    profile = args.profile or defaults.default_profile
    seed = args.seed if args.seed is not None else defaults.default_seed
    resume = defaults.resume if args.resume is None else args.resume
    retry_failures = (
        defaults.retry_failures
        if args.retry_failures is None
        else args.retry_failures
    )
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else defaults.output_root / args.run_group
    )
    cache_dir = (
        args.cache_dir.resolve()
        if args.cache_dir is not None
        else defaults.cache_dir
    )

    config = RunnerConfig(
        run_group=args.run_group,
        profile=profile,
        model_keys=model_keys,
        capability_ids=capability_ids,
        seed=seed,
        resume=resume,
        retry_failures=retry_failures,
        run_id=args.run_id,
    )
    runtime_resolver = RegistryRuntimeResolver(os.environ)
    runner = CapabilityRunner(
        suite=bundle,
        runtime_resolver=runtime_resolver,
        evidence_store=EvidenceStore(output_dir),
        cache_dir=cache_dir,
        environ=os.environ,
    )
    summary = runner.run(config)
    write_run_artifacts(
        suite=bundle,
        config=config,
        summary=summary,
        output_dir=output_dir,
    )
    _json(summary)
    return 0 if summary.failed_cases == 0 and summary.model_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
