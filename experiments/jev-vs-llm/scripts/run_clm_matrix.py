"""Autonomous CLM benchmark runner aligned with RUN_EXPERIMENTS.md."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from benchmark_core.config import ConfigError, parse_csv_selection
from benchmark_core.reporting import summarize_records
from benchmark_core.runner import BenchmarkArm, execute_arm
from rich.console import Console

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jev_bench.benchmark_data import DEFAULT_CACHE, prepare_public_data
from jev_bench.cli import (
    PUBLIC_PROFILES,
    _record_manifest,
    _tag_run,
    append_results,
    build_report,
)
from jev_bench.providers.clm import CLMProvider
from scripts.clm_manager import CLMEndpoint
from scripts.experiment_execution import run_single_experiment

console = Console()
DEFAULT_OUTPUT = PROJECT_ROOT / "results/raw/clm_results.csv"
DEFAULT_REPORT = PROJECT_ROOT / "results/clm_report.html"


def _models(value: str) -> list[str]:
    try:
        return parse_csv_selection(value)
    except ConfigError as exc:
        raise ValueError("At least one CLM model/checkpoint name is required") from exc


def _experiments(value: str, dataset: str) -> list[str]:
    raw = value.strip().lower()
    if raw == "all":
        return (
            ["routing", "calibration"]
            if dataset == "public"
            else ["routing", "calibration", "scaling", "workflow", "agent"]
        )

    experiments = [item.strip() for item in raw.split(",") if item.strip()]
    allowed = {"routing", "calibration", "scaling", "workflow", "agent"}
    unknown = [item for item in experiments if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown experiment(s): {', '.join(unknown)}")
    if dataset == "public":
        unsupported = [item for item in experiments if item not in {"routing", "calibration"}]
        if unsupported:
            raise ValueError(
                "Public dataset tier supports only routing and calibration; got "
                + ", ".join(unsupported)
            )
    if not experiments:
        raise ValueError("At least one experiment is required")
    return experiments


def _summary(
    frame: pd.DataFrame,
    *,
    model: str,
    experiment: str,
    elapsed_s: float,
) -> dict[str, Any]:
    summary = summarize_records(frame.to_dict(orient="records"))
    return {
        "model": model,
        "experiment": experiment,
        "status": "SUCCESS",
        "total_cases": summary["total_cases"],
        "valid_cases": summary["valid_cases"],
        "accuracy_pct": summary["accuracy_pct"],
        "avg_latency_ms": summary["avg_latency_ms"],
        "duration_s": round(elapsed_s, 1),
    }


def _print_summary(
    records: list[dict[str, Any]],
    report: Path,
    output: Path,
    group: str,
) -> None:
    console.print("\n" + "=" * 70)
    console.print("                      FINAL CLM SUMMARY")
    console.print("=" * 70)
    console.print(
        f"{'Model':<24} {'Exp':<12} {'Valid':<12} {'Accuracy':<10} {'Latency':<10}"
    )
    console.print("-" * 70)
    for record in records:
        if record.get("status") == "SUCCESS":
            valid_text = f"{record['valid_cases']}/{record['total_cases']}"
            console.print(
                f"{record['model']:<24} {record['experiment']:<12} "
                f"{valid_text:<12} {str(record['accuracy_pct']) + '%':<10} "
                f"{str(record['avg_latency_ms']) + 'ms':<10}"
            )
        else:
            console.print(
                f"{record['model']:<24} {record.get('experiment', 'N/A'):<12} "
                f"{'FAILED':<12} {record.get('error', '')}"
            )
    console.print("=" * 70)
    console.print(f"HTML Dashboard : file://{report.resolve()}")
    console.print(f"Raw Results CSV: {output.resolve()}")
    console.print(f"Run Group      : {group}")
    console.print("=" * 70 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CLM benchmarks with the same workflow as RUN_EXPERIMENTS.md.",
    )
    parser.add_argument(
        "-m",
        "--models",
        default=os.getenv("CLM_MODEL", "clm-latest"),
        help="Comma-separated CLM checkpoint names served by one endpoint.",
    )
    parser.add_argument(
        "-e",
        "--experiments",
        default="routing",
        help="Comma-separated experiment names or 'all'. Default: routing.",
    )
    parser.add_argument(
        "-d",
        "--dataset",
        choices=["smoke", "public"],
        default="public",
        help="Benchmark tier. Default: public.",
    )
    parser.add_argument(
        "-p",
        "--profile",
        choices=["budget", "quick", "standard", "full"],
        default="budget",
        help="Public benchmark profile. Default: budget.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CLM_BASE_URL", "http://127.0.0.1:8700"),
        help="CLM server root URL.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("CLM_TEMPERATURE", "1.0")),
        help="CLM distribution temperature.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60")),
    )
    args = parser.parse_args()

    if args.profile not in PUBLIC_PROFILES:
        parser.error("profile must be budget, quick, standard, or full")
    if not 0 < args.temperature <= 100:
        parser.error("temperature must be in (0, 100]")
    if args.timeout <= 0:
        parser.error("timeout must be positive")

    try:
        models = _models(args.models)
        experiments = _experiments(args.experiments, args.dataset)
    except ValueError as exc:
        parser.error(str(exc))

    endpoint = CLMEndpoint(
        args.base_url,
        api_key=os.getenv("CLM_API_KEY"),
        timeout=args.timeout,
    )
    try:
        preflight = endpoint.preflight(models)
    except RuntimeError as exc:
        console.print(f"[bold red]CLM preflight failed:[/] {exc}")
        console.print(
            "Start or expose the CLM server first. "
            "The reference setup is documented in CLM.md."
        )
        return 2

    if preflight["mock"]:
        console.print("[bold red]Refusing to benchmark a CLM mock runtime.[/]")
        return 2
    if not preflight["embedder_healthy"]:
        console.print("[bold red]CLM is up but its embedding runtime is unhealthy.[/]")
        return 2

    os.environ["CLM_BASE_URL"] = endpoint.base_url
    os.environ["CLM_TEMPERATURE"] = str(args.temperature)
    os.environ["BENCHMARK_TIMEOUT_SECONDS"] = str(args.timeout)

    if args.dataset == "public":
        console.print("[dim]Checking public dataset cache (BANKING77 / CLINC150)...[/]")
        prepare_public_data(args.cache_dir)

    group_id = str(uuid.uuid4())
    all_frames: list[pd.DataFrame] = []
    records: list[dict[str, Any]] = []

    console.print("\n" + "=" * 70)
    console.print("                 AUTONOMOUS CLM BENCHMARK RUNNER")
    console.print("=" * 70)
    console.print(f"CLM endpoint       : {endpoint.base_url}")
    console.print(f"Models             : {', '.join(models)}")
    console.print(f"Experiments        : {', '.join(experiments)}")
    console.print(f"Dataset            : {args.dataset} (profile: {args.profile})")
    console.print(f"Temperature        : {args.temperature}")
    console.print(f"Run group          : {group_id}")
    console.print("=" * 70 + "\n")

    for model_index, model in enumerate(models, start=1):
        console.print("━" * 70)
        console.print(
            f"[bold white on blue] CLM MODEL [{model_index}/{len(models)}]: {model} [/]"
        )
        console.print("━" * 70)

        os.environ["CLM_MODEL"] = model
        provider = CLMProvider(
            model=model,
            base_url=endpoint.base_url,
            temperature=args.temperature,
        )

        for experiment in experiments:
            arm = BenchmarkArm(model_key=model, task_id=experiment)

            def run_and_persist(
                experiment: str = experiment,
                provider: CLMProvider = provider,
                model: str = model,
            ) -> pd.DataFrame:
                frame = run_single_experiment(
                    exp_name=experiment,
                    provider=provider,
                    model_name=model,
                    dataset=args.dataset,
                    profile=args.profile,
                    cache_dir=args.cache_dir,
                    seed=args.seed,
                )
                tagged_frame = _tag_run(
                    frame,
                    group_id,
                    f"{args.dataset}-{experiment}",
                )
                append_results(tagged_frame, args.output)
                return tagged_frame

            execution = execute_arm(arm, run_and_persist)
            if execution.succeeded:
                tagged = execution.value
                if not isinstance(tagged, pd.DataFrame):
                    raise TypeError("benchmark arm did not return a DataFrame")
                all_frames.append(tagged)

                record = _summary(
                    tagged,
                    model=model,
                    experiment=experiment,
                    elapsed_s=execution.elapsed_s,
                )
                records.append(record)
                console.print(
                    f"\n[bold green]✓ Done {model}[/] on "
                    f"[bold yellow]{experiment}[/] in [cyan]{execution.elapsed_s:.1f}s[/] "
                    f"| Acc: [bold]{record['accuracy_pct']}%[/] "
                    f"| Valid: [bold]{record['valid_cases']}/{record['total_cases']}[/] "
                    f"| Latency: [cyan]{record['avg_latency_ms']}ms[/]\n"
                )
            else:
                error = f"{execution.error_type}: {execution.error_message}"
                records.append(
                    {
                        "model": model,
                        "experiment": experiment,
                        "status": "ERROR_EXECUTION",
                        "error": error,
                    }
                )
                console.print(f"[bold red]✗ Failed {model} on {experiment}:[/] {error}")

    if not all_frames:
        console.print("[bold red]No benchmark arm completed successfully.[/]")
        return 1

    combined = pd.concat(all_frames, ignore_index=True)
    _record_manifest(
        combined,
        group=group_id,
        suite=f"clm-{args.dataset}",
        parameters={
            "models": models,
            "experiments": experiments,
            "dataset": args.dataset,
            "profile": args.profile if args.dataset == "public" else None,
            "seed": args.seed,
            "clm_base_url": endpoint.base_url,
            "clm_temperature": args.temperature,
            "clm_served_models": preflight["served_models"],
            "clm_embedder_healthy": preflight["embedder_healthy"],
        },
        requested_openai_models=[],
        requested_minicpm_models=[],
        requested_clm_models=models,
        requested_korgis_models=[],
    )
    build_report(args.output, args.report, run_group=group_id)
    _print_summary(records, args.report, args.output, group_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
