from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from benchmark_core import (
    create_run_identity,
    parse_csv_selection,
    preflight_models,
    to_jsonable,
)

from model_capability_bench.analytics.dashboard_build import build_dashboard
from model_capability_bench.analytics.dashboard_export import export_dashboard_data
from model_capability_bench.analytics.projector import project_results
from model_capability_bench.reporting import (
    load_benchmark_report,
    load_reporting_config,
    write_report,
)
from model_capability_bench.runner import (
    CapabilityRunner,
    EvidenceStore,
    RunnerConfig,
    estimate_benchmark,
    expand_sweep,
    load_sweep,
)
from model_capability_bench.runner.config import load_runner_defaults
from model_capability_bench.runner.manifest import write_run_artifacts
from model_capability_bench.runner.planning import plan_benchmark
from model_capability_bench.runner.progress import TerminalProgress
from model_capability_bench.runtimes import RegistryRuntimeResolver
from model_capability_bench.sharing import create_share_snapshot, render_share_snapshot
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
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show live status, case progress and estimated remaining time on stderr.",
    )
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

    estimate = sub.add_parser(
        "estimate",
        help="Run a small pilot and project runtime/cost for a benchmark tier.",
    )
    estimate.add_argument("--models", default="all")
    estimate.add_argument("--capabilities", default="all")
    estimate.add_argument("--profile")
    estimate.add_argument("--pilot-cases", type=int, default=5)
    estimate.add_argument("--seed", type=int)
    estimate.add_argument("--cache-dir", type=Path)

    sweep = sub.add_parser(
        "sweep",
        help="Execute a controlled parameter-sensitivity experiment for one model.",
    )
    sweep.add_argument("--model", required=True)
    sweep.add_argument("--sweep", default="generation-sensitivity")
    sweep.add_argument("--capabilities", default="all")
    sweep.add_argument("--profile")
    sweep.add_argument("--seed", type=int)
    sweep.add_argument("--run-group", required=True)
    sweep.add_argument("--output-root", type=Path)
    sweep.add_argument("--cache-dir", type=Path)
    sweep.add_argument("--plan-only", action="store_true")
    sweep.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    validate = sub.add_parser(
        "validate-config",
        help="Validate suite composition and provider environment.",
    )
    validate.add_argument("--models", default="all")

    plan = sub.add_parser(
        "plan",
        help="Show vertical case counts and configured budgets without inference.",
    )
    plan.add_argument("--capabilities", default="all")
    plan.add_argument("--profile")

    report = sub.add_parser(
        "report",
        help="Render a persisted run without invoking models or providers.",
    )
    report.add_argument("--run-dir", type=Path, required=True)
    report.add_argument("--html", type=Path)
    report.add_argument("--json", type=Path)

    project = sub.add_parser(
        "project",
        help="Build or refresh the rebuildable cross-run DuckDB analytics model.",
    )
    project.add_argument("--results-root", type=Path)
    project.add_argument("--database", type=Path)
    project.add_argument("--run-dir", type=Path, action="append")
    project.add_argument("--rebuild", action="store_true")
    project.add_argument("--export-dashboard", action="store_true")

    dashboard_data = sub.add_parser(
        "dashboard-data",
        help="Export typed dashboard JSON from the analytics database.",
    )
    dashboard_data.add_argument("--results-root", type=Path)
    dashboard_data.add_argument("--database", type=Path)
    dashboard_data.add_argument("--output-dir", type=Path)

    dashboard_build = sub.add_parser(
        "dashboard-build",
        help="Build a single-file dashboard with projected CURRENT payloads.",
    )
    dashboard_build.add_argument("--results-root", type=Path)
    dashboard_build.add_argument("--data-dir", type=Path)
    dashboard_build.add_argument("--output", type=Path)
    dashboard_build.add_argument(
        "--capability",
        default="structured-output",
    )

    share = sub.add_parser(
        "share",
        help="Create immutable share artifacts from projected CURRENT results.",
    )
    share_sub = share.add_subparsers(dest="share_command", required=True)
    share_create = share_sub.add_parser(
        "create",
        help="Freeze one comparable capability result into a share snapshot.",
    )
    share_create.add_argument("--capability", required=True)
    share_create.add_argument("--models", required=True)
    share_create.add_argument("--title")
    share_create.add_argument("--results-root", type=Path)
    share_create.add_argument("--database", type=Path)

    share_render = share_sub.add_parser(
        "render",
        help="Render an immutable share snapshot into PNG cards and/or PDF.",
    )
    share_render.add_argument("--snapshot", required=True)
    share_render.add_argument("--format", default="png,pdf")
    share_render.add_argument("--results-root", type=Path)
    share_render.add_argument("--chrome")

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

    if args.command == "project":
        results_root = (
            args.results_root.resolve()
            if args.results_root is not None
            else root / "results"
        )
        database = (
            args.database.resolve()
            if args.database is not None
            else results_root / "analytics" / "benchmark.duckdb"
        )
        summary = project_results(
            results_root=results_root,
            database_path=database,
            rebuild=args.rebuild,
            run_dirs=(
                tuple(path.resolve() for path in args.run_dir)
                if args.run_dir
                else None
            ),
        )
        payload: dict[str, Any] = {"projection": summary}
        if args.export_dashboard:
            payload["dashboard"] = export_dashboard_data(
                database_path=database,
                output_dir=results_root / "analytics" / "dashboard",
            )
        _json(payload)
        return 0

    if args.command == "dashboard-data":
        results_root = (
            args.results_root.resolve()
            if args.results_root is not None
            else root / "results"
        )
        database = (
            args.database.resolve()
            if args.database is not None
            else results_root / "analytics" / "benchmark.duckdb"
        )
        output_dir = (
            args.output_dir.resolve()
            if args.output_dir is not None
            else results_root / "analytics" / "dashboard"
        )
        _json(
            export_dashboard_data(
                database_path=database,
                output_dir=output_dir,
            )
        )
        return 0

    if args.command == "dashboard-build":
        results_root = (
            args.results_root.resolve()
            if args.results_root is not None
            else root / "results"
        )
        data_dir = (
            args.data_dir.resolve()
            if args.data_dir is not None
            else results_root / "analytics" / "dashboard"
        )
        output = (
            args.output.resolve()
            if args.output is not None
            else results_root / "analytics" / "dashboard.html"
        )
        _json(
            build_dashboard(
                root=root,
                dashboard_data_dir=data_dir,
                output_path=output,
                capability_id=args.capability,
            )
        )
        return 0

    if args.command == "share":
        results_root = (
            args.results_root.resolve()
            if args.results_root is not None
            else root / "results"
        )
        if args.share_command == "create":
            database = (
                args.database.resolve()
                if args.database is not None
                else results_root / "analytics" / "benchmark.duckdb"
            )
            model_keys = tuple(
                value.strip()
                for value in args.models.split(",")
                if value.strip()
            )
            _json(
                create_share_snapshot(
                    results_root=results_root,
                    database_path=database,
                    capability_id=args.capability,
                    model_keys=model_keys,
                    title=args.title,
                )
            )
            return 0

        if args.share_command == "render":
            snapshot_arg = Path(args.snapshot)
            snapshot_path = (
                snapshot_arg.resolve()
                if snapshot_arg.is_file()
                else results_root / "shares" / args.snapshot / "snapshot.json"
            )
            formats = tuple(
                value.strip()
                for value in args.format.split(",")
                if value.strip()
            )
            _json(
                render_share_snapshot(
                    snapshot_path=snapshot_path,
                    formats=formats,
                    chrome_binary=args.chrome,
                )
            )
            return 0

        raise ValueError(f"Unsupported share command: {args.share_command}")

    if args.command == "report":
        reporting_config = load_reporting_config(root)
        run_dir = args.run_dir.resolve()
        report = load_benchmark_report(run_dir, reporting_config)
        outputs = write_report(
            report,
            reporting_config,
            run_dir,
            html_path=args.html.resolve() if args.html is not None else None,
            json_path=args.json.resolve() if args.json is not None else None,
        )
        _json(
            {
                "run_id": report.run_id,
                "html_path": outputs.html_path,
                "json_path": outputs.json_path,
            }
        )
        return 0

    bundle = load_capability_suite(root)
    defaults = load_runner_defaults(root)

    if args.command in {"models", "tasks", "datasets", "capabilities"}:
        _json(_catalog_payload(bundle, args.command))
        return 0

    if args.command == "plan":
        capability_ids = _selection(
            args.capabilities,
            [
                capability.spec.capability_id
                for capability in bundle.resolved_capabilities
            ],
        )
        profile = args.profile or defaults.default_profile
        _json(
            plan_benchmark(
                bundle,
                profile_id=profile,
                capability_ids=capability_ids,
            )
        )
        return 0

    available_models = list(bundle.models.models)

    if args.command == "sweep":
        if args.model not in available_models:
            raise ValueError(
                f"Unknown model {args.model!r}; available: "
                + ", ".join(sorted(available_models))
            )
        capability_ids = _selection(
            args.capabilities,
            [
                capability.spec.capability_id
                for capability in bundle.resolved_capabilities
            ],
        )
        profile = args.profile or defaults.default_profile
        seed = args.seed if args.seed is not None else defaults.default_seed
        cache_dir = (
            args.cache_dir.resolve()
            if args.cache_dir is not None
            else defaults.cache_dir
        )
        sweep_spec = load_sweep(root, args.sweep)
        points = expand_sweep(sweep_spec)
        if args.plan_only:
            _json(
                {
                    "sweep_id": args.sweep,
                    "strategy": sweep_spec.strategy,
                    "model": args.model,
                    "point_count": len(points),
                    "points": points,
                }
            )
            return 0

        output_root = (
            args.output_root.resolve()
            if args.output_root is not None
            else defaults.output_root
        )
        results: list[dict[str, Any]] = []
        failed = False
        for point in points:
            identity = create_run_identity(
                run_group=args.run_group,
                suite=bundle.suite.suite_id,
                runner_location="model-capability-benchmark",
            )
            output_dir = output_root / identity.run_id
            config = RunnerConfig(
                run_group=args.run_group,
                profile=profile,
                model_keys=(args.model,),
                capability_ids=capability_ids,
                seed=seed,
                resume=defaults.resume,
                retry_failures=defaults.retry_failures,
                run_id=identity.run_id,
                configuration_id=point.configuration_id,
                inference_config=point.inference_config,
                runtime_config=point.runtime_config,
                metadata={
                    "experiment_kind": "sensitivity",
                    "sweep_id": point.sweep_id,
                    "sweep_label": point.label,
                    "changed_dimension": point.changed_dimension,
                    "is_baseline": point.is_baseline,
                },
            )
            with TerminalProgress(enabled=args.progress) as progress:
                runner = CapabilityRunner(
                    suite=bundle,
                    runtime_resolver=RegistryRuntimeResolver(os.environ),
                    evidence_store=EvidenceStore(
                        output_dir,
                        on_event=progress.on_event,
                    ),
                    cache_dir=cache_dir,
                    environ=os.environ,
                )
                summary = runner.run(config)
                progress.phase("writing manifest")
                write_run_artifacts(
                    suite=bundle,
                    config=config,
                    summary=summary,
                    output_dir=output_dir,
                )
                progress.phase("rendering report")
                reporting_config = load_reporting_config(root)
                report = load_benchmark_report(output_dir, reporting_config)
                outputs = write_report(report, reporting_config, output_dir)
            failed = (
                failed
                or summary.failed_cases > 0
                or summary.model_failures > 0
            )
            results.append(
                {
                    "configuration_id": point.configuration_id,
                    "label": point.label,
                    "changed_dimension": point.changed_dimension,
                    "is_baseline": point.is_baseline,
                    "run_id": summary.run_id,
                    "summary": summary,
                    "report": {
                        "html_path": outputs.html_path,
                        "json_path": outputs.json_path,
                    },
                }
            )
        _json(
            {
                "sweep_id": args.sweep,
                "model": args.model,
                "point_count": len(points),
                "results": results,
            }
        )
        return 1 if failed else 0

    model_keys = _selection(args.models, available_models)

    if args.command == "estimate":
        capability_ids = _selection(
            args.capabilities,
            [
                capability.spec.capability_id
                for capability in bundle.resolved_capabilities
            ],
        )
        profile = args.profile or defaults.default_profile
        seed = args.seed if args.seed is not None else defaults.default_seed
        cache_dir = (
            args.cache_dir.resolve()
            if args.cache_dir is not None
            else defaults.cache_dir
        )
        runtime_resolver = RegistryRuntimeResolver(os.environ)
        _json(
            estimate_benchmark(
                bundle,
                runtime_resolver=runtime_resolver,
                cache_dir=cache_dir,
                environ=os.environ,
                profile_id=profile,
                model_keys=model_keys,
                capability_ids=capability_ids,
                pilot_cases=args.pilot_cases,
                seed=seed,
            )
        )
        return 0

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
    resolved_run_id = args.run_id
    if resolved_run_id is None:
        resolved_run_id = create_run_identity(
            run_group=args.run_group,
            suite=bundle.suite.suite_id,
            runner_location="model-capability-benchmark",
        ).run_id
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else defaults.output_root / resolved_run_id
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
        run_id=resolved_run_id,
    )
    with TerminalProgress(enabled=args.progress) as progress:
        runtime_resolver = RegistryRuntimeResolver(os.environ)
        runner = CapabilityRunner(
            suite=bundle,
            runtime_resolver=runtime_resolver,
            evidence_store=EvidenceStore(output_dir, on_event=progress.on_event),
            cache_dir=cache_dir,
            environ=os.environ,
        )
        summary = runner.run(config)
        progress.phase("writing manifest")
        write_run_artifacts(
            suite=bundle,
            config=config,
            summary=summary,
            output_dir=output_dir,
        )
        progress.phase("rendering report")
        reporting_config = load_reporting_config(root)
        report = load_benchmark_report(output_dir, reporting_config)
        outputs = write_report(
            report,
            reporting_config,
            output_dir,
        )
    _json(
        {
            "summary": summary,
            "report": {
                "html_path": outputs.html_path,
                "json_path": outputs.json_path,
            },
        }
    )
    return 0 if summary.failed_cases == 0 and summary.model_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
