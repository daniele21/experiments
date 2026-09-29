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
from jev_bench.clm_runtime import CLMLocalRuntimeManager, load_clm_runtime_spec
from jev_bench.providers.clm import CLMProvider
from scripts.clm_manager import CLMEndpoint
from scripts.experiment_execution import run_single_experiment

console = Console()
DEFAULT_OUTPUT = PROJECT_ROOT / "results/raw/clm_results.csv"
DEFAULT_REPORT = PROJECT_ROOT / "results/clm_report.html"
DEFAULT_RUNTIME_CONFIG = PROJECT_ROOT / "clm_runtimes.yaml"


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
        f"{'Model':<28} {'Exp':<12} {'Valid':<12} {'Accuracy':<10} {'Latency':<10}"
    )
    console.print("-" * 74)
    for record in records:
        if record.get("status") == "SUCCESS":
            valid_text = f"{record['valid_cases']}/{record['total_cases']}"
            console.print(
                f"{record['model']:<28} {record['experiment']:<12} "
                f"{valid_text:<12} {str(record['accuracy_pct']) + '%':<10} "
                f"{str(record['avg_latency_ms']) + 'ms':<10}"
            )
        else:
            console.print(
                f"{record['model']:<28} {record.get('experiment', 'N/A'):<12} "
                f"{'FAILED':<12} {record.get('error', '')}"
            )
    console.print("=" * 74)
    console.print(f"HTML Dashboard : file://{report.resolve()}")
    console.print(f"Raw Results CSV: {output.resolve()}")
    console.print(f"Run Group      : {group}")
    console.print("=" * 74 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CLM benchmarks with the same workflow as RUN_EXPERIMENTS.md.",
    )
    parser.add_argument(
        "-m",
        "--models",
        default=None,
        help=(
            "Comma-separated CLM checkpoint names served by one endpoint. "
            "Managed runtimes default to the checkpoint declared in clm_runtimes.yaml."
        ),
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
        help="CLM server root URL for externally managed runtimes.",
    )
    parser.add_argument(
        "--runtime",
        help=(
            "Managed local CLM runtime id from clm_runtimes.yaml, e.g. "
            "clm-v0.1-8b-q4km-outq2."
        ),
    )
    parser.add_argument(
        "--runtime-config",
        type=Path,
        default=DEFAULT_RUNTIME_CONFIG,
        help="CLM local runtime registry YAML.",
    )
    parser.add_argument(
        "--encoder-path",
        type=Path,
        help="Path to the managed runtime GGUF. Overrides its path_env setting.",
    )
    parser.add_argument(
        "--llama-server-bin",
        help="llama-server executable. Defaults to CLM_LLAMA_SERVER_BIN/LOCAL_LLM_SERVER_BIN/PATH.",
    )
    parser.add_argument(
        "--clm-serve-bin",
        help="clm-serve executable. Defaults to CLM_SERVE_BIN/PATH.",
    )
    parser.add_argument(
        "--clm-checkpoint",
        type=Path,
        help="Optional CLM head checkpoint. Otherwise the upstream default head is used.",
    )
    parser.add_argument(
        "--runtime-startup-timeout",
        type=float,
        default=float(os.getenv("CLM_RUNTIME_STARTUP_TIMEOUT_SECONDS", "300")),
        help="Seconds allowed for llama-server and clm-serve startup.",
    )
    parser.add_argument(
        "--keep-runtime",
        action="store_true",
        help="Leave a managed local CLM runtime running after the benchmark exits.",
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
    if args.runtime_startup_timeout <= 0:
        parser.error("runtime-startup-timeout must be positive")

    runtime_spec = None
    runtime_manager: CLMLocalRuntimeManager | None = None
    runtime_identity: dict[str, Any] = {}

    try:
        experiments = _experiments(args.experiments, args.dataset)
        if args.runtime:
            runtime_spec = load_clm_runtime_spec(args.runtime_config, args.runtime)
            models = _models(args.models or runtime_spec.served_model)
            incompatible = [model for model in models if model != runtime_spec.served_model]
            if incompatible:
                raise ValueError(
                    f"Managed runtime {runtime_spec.runtime_id!r} serves "
                    f"{runtime_spec.served_model!r}; incompatible requested model(s): "
                    + ", ".join(incompatible)
                )
        else:
            models = _models(args.models or os.getenv("CLM_MODEL", "clm-latest"))
    except (ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))

    endpoint_url = args.base_url
    if runtime_spec is not None:
        runtime_manager = CLMLocalRuntimeManager(
            runtime_spec,
            encoder_path=args.encoder_path,
            llama_server_bin=args.llama_server_bin,
            clm_serve_bin=args.clm_serve_bin,
            clm_checkpoint=args.clm_checkpoint,
            startup_timeout=args.runtime_startup_timeout,
            log_dir=PROJECT_ROOT / "results/logs",
        )
        console.print(
            f"[bold cyan]Starting managed CLM runtime[/] "
            f"[bold]{runtime_spec.runtime_id}[/]..."
        )
        try:
            runtime_identity = runtime_manager.start()
        except RuntimeError as exc:
            console.print(f"[bold red]Managed CLM runtime failed:[/] {exc}")
            return 2
        endpoint_url = runtime_manager.clm_base_url

    endpoint = CLMEndpoint(
        endpoint_url,
        api_key=os.getenv("CLM_API_KEY"),
        timeout=args.timeout,
    )
    try:
        preflight = endpoint.preflight(models)
    except RuntimeError as exc:
        if runtime_manager is not None:
            runtime_manager.stop()
        console.print(f"[bold red]CLM preflight failed:[/] {exc}")
        console.print(
            "Start/expose the CLM server first, or use --runtime for a managed GGUF runtime. "
            "See CLM.md."
        )
        return 2

    if preflight["mock"]:
        if runtime_manager is not None:
            runtime_manager.stop()
        console.print("[bold red]Refusing to benchmark a CLM mock runtime.[/]")
        return 2
    if not preflight["embedder_healthy"]:
        if runtime_manager is not None:
            runtime_manager.stop()
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
    benchmark_model_ids = {
        model: (
            runtime_spec.benchmark_model_id
            if runtime_spec is not None
            else model
        )
        for model in models
    }

    console.print("\n" + "=" * 74)
    console.print("                 AUTONOMOUS CLM BENCHMARK RUNNER")
    console.print("=" * 74)
    console.print(f"CLM endpoint       : {endpoint.base_url}")
    console.print(f"Served model(s)    : {', '.join(models)}")
    console.print(
        "Benchmark model(s) : "
        + ", ".join(benchmark_model_ids[model] for model in models)
    )
    if runtime_spec is not None:
        console.print(f"Managed runtime    : {runtime_spec.runtime_id}")
    console.print(f"Experiments        : {', '.join(experiments)}")
    console.print(f"Dataset            : {args.dataset} (profile: {args.profile})")
    console.print(f"Temperature        : {args.temperature}")
    console.print(f"Run group          : {group_id}")
    console.print("=" * 74 + "\n")

    for model_index, model in enumerate(models, start=1):
        benchmark_model_id = benchmark_model_ids[model]
        console.print("━" * 74)
        console.print(
            f"[bold white on blue] CLM MODEL [{model_index}/{len(models)}]: "
            f"{benchmark_model_id} [/]"
        )
        console.print("━" * 74)

        os.environ["CLM_MODEL"] = model
        provider = CLMProvider(
            model=model,
            base_url=endpoint.base_url,
            temperature=args.temperature,
            benchmark_model_id=benchmark_model_id,
        )

        for experiment in experiments:
            arm = BenchmarkArm(model_key=benchmark_model_id, task_id=experiment)

            def run_and_persist(
                experiment: str = experiment,
                provider: CLMProvider = provider,
                benchmark_model_id: str = benchmark_model_id,
            ) -> pd.DataFrame:
                frame = run_single_experiment(
                    exp_name=experiment,
                    provider=provider,
                    model_name=benchmark_model_id,
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
                    model=benchmark_model_id,
                    experiment=experiment,
                    elapsed_s=execution.elapsed_s,
                )
                records.append(record)
                console.print(
                    f"\n[bold green]✓ Done {benchmark_model_id}[/] on "
                    f"[bold yellow]{experiment}[/] in [cyan]{execution.elapsed_s:.1f}s[/] "
                    f"| Acc: [bold]{record['accuracy_pct']}%[/] "
                    f"| Valid: [bold]{record['valid_cases']}/{record['total_cases']}[/] "
                    f"| Latency: [cyan]{record['avg_latency_ms']}ms[/]\n"
                )
            else:
                error = f"{execution.error_type}: {execution.error_message}"
                records.append(
                    {
                        "model": benchmark_model_id,
                        "experiment": experiment,
                        "status": "ERROR_EXECUTION",
                        "error": error,
                    }
                )
                console.print(
                    f"[bold red]✗ Failed {benchmark_model_id} on {experiment}:[/] {error}"
                )

    if not all_frames:
        if runtime_manager is not None and not args.keep_runtime:
            runtime_manager.stop()
        elif runtime_manager is not None:
            runtime_manager.detach()
        console.print("[bold red]No benchmark arm completed successfully.[/]")
        return 1

    combined = pd.concat(all_frames, ignore_index=True)
    requested_benchmark_models = [benchmark_model_ids[model] for model in models]
    _record_manifest(
        combined,
        group=group_id,
        suite=f"clm-{args.dataset}",
        parameters={
            "models": requested_benchmark_models,
            "clm_served_models_requested": models,
            "experiments": experiments,
            "dataset": args.dataset,
            "profile": args.profile if args.dataset == "public" else None,
            "seed": args.seed,
            "clm_base_url": endpoint.base_url,
            "clm_temperature": args.temperature,
            "clm_served_models": preflight["served_models"],
            "clm_embedder_healthy": preflight["embedder_healthy"],
            "clm_runtime_identity": runtime_identity or None,
        },
        requested_openai_models=[],
        requested_minicpm_models=[],
        requested_clm_models=requested_benchmark_models,
        requested_korgis_models=[],
    )
    build_report(args.output, args.report, run_group=group_id)
    _print_summary(records, args.report, args.output, group_id)

    if runtime_manager is not None:
        if args.keep_runtime:
            runtime_manager.detach()
            console.print(
                f"[yellow]Managed CLM runtime left running at {runtime_manager.clm_base_url}[/]"
            )
        else:
            runtime_manager.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
