"""Sequential Decisio launcher using the benchmark's terminal presentation.

Inference stays in Decisio's pinned environment; Rich and orchestration run in
the benchmark environment. Worker events never change the scoring algorithm.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from jev_bench.cli import PUBLIC_PROFILES
from jev_bench.decisio_results import publish_decisio_results
from jev_bench.progress import should_show_progress

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = ["qwen3.5-2b-q4km", "qwen3.5-4b-q4km"]
EVENT_PREFIX = "DECISIO_EVENT "


def add_decisio_options(parser):
    group = parser.add_argument_group("Decisio (--provider decisio)")
    group.add_argument(
        "--decisio-root", type=Path, help="Decisio checkout; default: sibling repository"
    )
    group.add_argument(
        "--decisio-python", type=Path, help="Default: <decisio-root>/.venv/bin/python"
    )
    group.add_argument("--methods", help="Default: direct,json (smoke), semantic,json (public)")
    group.add_argument(
        "--device",
        choices=["cpu", "metal"],
        help="Inference device (default: metal on macOS, cpu elsewhere)",
    )
    group.add_argument("--threads", type=int, help="CPU threads (default: 4)")
    group.add_argument("--cases", type=int, help="Override the number of routing cases")
    group.add_argument("--output", type=Path, help="New run directory; default: unique timestamp")
    group.add_argument(
        "--resume", type=Path, help="Resume a matrix directory or an old single-model run"
    )
    group.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Live bars; automatic in terminals, plain events in logs",
    )


def build_plan(args, registry):
    """Validate the complete matrix before starting any subprocess or writing outputs."""
    if args.experiments not in (None, "routing", "all"):
        raise ValueError("Decisio currently supports only --experiments routing")
    if args.thinking or args.clean or args.keep_korgis:
        raise ValueError("Decisio does not support --thinking, --clean or --keep-korgis")
    if args.resume and args.output:
        raise ValueError("use --resume OR --output")
    if args.interactive:
        raise ValueError("select Decisio models with --models")
    saved = None
    single = False
    directory = args.resume or args.output
    if args.resume:
        if (directory / "matrix.json").is_file():
            saved = json.loads((directory / "matrix.json").read_text())
        elif (directory / "manifest.json").is_file():
            single = True
            manifest = json.loads((directory / "manifest.json").read_text())
            matches = [
                key
                for key, value in registry.items()
                if Path(value.get("path", "")).expanduser().resolve()
                == Path(manifest["config"]["model"]).expanduser().resolve()
            ]
            if not matches:
                raise ValueError("saved GGUF is not in benchmark-models.yaml")
            fixture = json.loads((directory / "fixture.json").read_text())
            saved = {
                "models": matches[:1],
                "dataset": "public" if manifest["dataset"] == "banking77" else "smoke",
                "profile": "budget",
                "cases": len(fixture["cases"]),
                "methods": manifest["methods"],
                "device": manifest["config"].get("device", "cpu"),
                "threads": manifest["config"]["n_threads"],
            }
        else:
            raise ValueError(
                "--resume requires a directory containing matrix.json or manifest.json"
            )
    saved = saved or {}
    models = (
        args.models.split(",")
        if args.models and args.models != "all"
        else DEFAULT_MODELS
        if args.models == "all"
        else saved.get("models", DEFAULT_MODELS)
    )
    models = [model.strip() for model in models]
    if len(set(models)) != len(models) or not models or any(m not in registry for m in models):
        raise ValueError("--models must contain unique keys from --list")
    dataset = args.dataset or saved.get("dataset", "smoke")
    profile = args.profile or saved.get("profile", "budget")
    case_count = (
        args.cases
        if args.cases is not None
        else saved.get("cases", PUBLIC_PROFILES[profile]["routing"] if dataset == "public" else 24)
    )
    if args.profile is not None and args.cases is None:
        case_count = PUBLIC_PROFILES[profile]["routing"] if dataset == "public" else 24
    methods = (
        args.methods.split(",")
        if args.methods
        else saved.get(
            "methods", ["semantic", "json"] if dataset == "public" else ["direct", "json"]
        )
    )
    if (
        not methods
        or len(set(methods)) != len(methods)
        or not set(methods) <= {"direct", "fresh", "semantic", "json"}
    ):
        raise ValueError("--methods must be unique values from direct,fresh,semantic,json")
    if dataset == "public" and set(methods) & {"direct", "fresh"}:
        raise ValueError(
            "BANKING77 has 77 classes; native direct/fresh supports only 26. Use semantic,json"
        )
    threads = args.threads if args.threads is not None else saved.get("threads", 4)
    device = getattr(args, "device", None) or saved.get(
        "device", "metal" if sys.platform == "darwin" else "cpu"
    )
    if threads < 1 or (case_count is not None and case_count < 1):
        raise ValueError("--threads and --cases must be positive")
    plan = {
        "models": models,
        "dataset": dataset,
        "profile": profile,
        "cases": case_count,
        "methods": methods,
        "device": device,
        "threads": threads,
    }
    if args.resume:
        for key in ("models", "dataset", "cases", "methods", "device", "threads"):
            saved_value = saved.get(key, "cpu" if key == "device" else None)
            if saved_value != plan[key]:
                raise ValueError(f"cannot resume: {key} differs from the saved run")
    decisio_root = (
        (args.decisio_root or Path(saved.get("decisio_root", ROOT.parents[2] / "decisio")))
        .expanduser()
        .resolve()
    )
    python = (
        (
            args.decisio_python
            or Path(saved.get("decisio_python", decisio_root / ".venv/bin/python"))
        )
        .expanduser()
        .absolute()
    )
    if not (decisio_root / "src/decisio").is_dir() or not python.is_file():
        raise ValueError(
            "Decisio checkout/environment not found; set --decisio-root and/or --decisio-python"
        )
    for model in models:
        path = Path(registry[model].get("path", "")).expanduser()
        if path.suffix.lower() != ".gguf" or not path.is_file():
            raise ValueError(f"GGUF not found for {model}: {path}")
    if directory is None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        directory = ROOT / "results/decisio" / f"{stamp}-{uuid4().hex[:8]}"
    directory = directory.expanduser().absolute()
    if directory.exists() and not args.resume:
        raise ValueError(f"output already exists: {directory}; use --resume or a new --output")
    plan.update(decisio_root=str(decisio_root), decisio_python=str(python))
    return plan, directory, single


def worker_command(plan, model_path, output, *, resume):
    command = [
        plan["decisio_python"],
        "-u",
        str(ROOT / "scripts/compare_decisio.py"),
        "--decisio-root",
        plan["decisio_root"],
        "--model",
        str(model_path),
        "--dataset",
        "banking77" if plan["dataset"] == "public" else "smoke",
        "--methods",
        ",".join(plan["methods"]),
        "--device",
        plan["device"],
        "--threads",
        str(plan["threads"]),
        "--output",
        str(output),
        "--events-json",
    ]
    if plan["cases"] is not None:
        command += ["--cases", str(plan["cases"])]
    if resume:
        command.append("--resume")
    return command


class RunDisplay:
    def __init__(self, console, model, show_progress):
        self.console, self.model = console, model
        self.active = should_show_progress(show_progress)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.fields[model]}[/]"),
            TextColumn("[bold yellow]{task.fields[method]}[/]"),
            BarColumn(bar_width=25),
            TaskProgressColumn(),
            TextColumn("{task.fields[counter]}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            TextColumn("[dim]{task.fields[status]}[/]"),
            console=console,
            disable=not self.active,
        )
        self.task = None
        self.summaries = {}

    def handle(self, event):
        kind = event["event"]
        method = event.get("method", "routing")
        if kind in {"phase", "method_start"}:
            if self.task is not None:
                self.progress.remove_task(self.task)
            phase = kind == "phase"
            status = (
                event["status"]
                if phase
                else (
                    f"resumed: {event['completed']} cases"
                    if event["completed"]
                    else "Starting cases..."
                )
            )
            self.task = self.progress.add_task(
                "run",
                total=None if phase else event["total"],
                completed=0 if phase else event["completed"],
                model=escape(self.model),
                method=method,
                status=escape(status),
                counter="" if phase else f"{event['completed']}/{event['total']}",
            )
            self.console.print(f"[dim]{escape(status)}[/]")
        elif kind == "case_start":
            self.progress.update(self.task, status=f"scoring {escape(event['case_id'])}")
            if not self.active:
                self.console.print(
                    f"  Scoring {event['completed'] + 1}/{event['total']}: "
                    f"{escape(event['case_id'])}"
                )
        elif kind == "case":
            badge = (
                "[green]✓ correct[/]"
                if event["correct"]
                else ("[yellow]✗ mismatch[/]" if event["valid"] else "[red]✗ invalid[/]")
            )
            self.console.print(
                f"  [{event['completed']:>3}/{event['total']}] {badge} "
                f"• {escape(event['case_id'])} • [cyan]{event['latency_ms']:.0f}ms[/] "
                f"• got: {escape(str(event['choice']))}, expected: {escape(str(event['expected']))}"
            )
            outcome = (
                "correct"
                if event["correct"]
                else ("mismatch" if event["valid"] else "invalid")
            )
            self.progress.update(
                self.task,
                completed=event["completed"],
                status=(
                    f"{outcome} {escape(event['case_id'])} | "
                    f"acc: {event['accuracy']:.1%} | lat: {event['latency_ms']:.0f}ms"
                ),
                counter=f"{event['completed']}/{event['total']}",
            )
        elif kind == "method_done":
            summary = event["summary"]
            self.summaries[method] = summary
            if self.task is not None:
                self.progress.update(self.task, status="done")
            self.console.print(
                f"[green]✓ Done {escape(self.model)}[/] on [yellow]{method}[/] "
                f"| Acc: {summary['accuracy']:.1%} "
                f"| Valid: {summary['valid_rate']:.1%} "
                f"| p50: {summary['latency_p50_ms']:.0f}ms"
            )


def run_worker(command, display):
    """Own and reap the worker, including interruption during native inference."""
    with display.progress:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, text=True, start_new_session=True, cwd=ROOT
        )
        try:
            for line in process.stdout:
                if line.startswith(EVENT_PREFIX):
                    display.handle(json.loads(line[len(EVENT_PREFIX) :]))
                else:
                    display.console.print(line.rstrip(), markup=False)
            return process.wait()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            process.stdout.close()


def run_matrix(args, registry):
    console = Console(force_terminal=True if args.progress else None)
    if args.list:
        for model in DEFAULT_MODELS:
            console.print(f"  • {model}: {registry.get(model, {}).get('path', 'not registered')}")
        return 0
    try:
        plan, directory, single = build_plan(args, registry)
    except (ValueError, KeyError, OSError) as exc:
        console.print(f"[red]Decisio configuration error:[/] {escape(str(exc))}")
        return 2
    if not args.resume:
        directory.mkdir(parents=True)
        (directory / "matrix.json").write_text(json.dumps(plan, indent=2))
    console.print("\n[bold magenta]🚀 Starting Decisio Benchmark Group[/]")
    console.print(
        f"   • Models: {', '.join(plan['models'])}\n"
        f"   • Experiment: routing | Dataset: {plan['dataset']} ({plan['profile']})\n"
        f"   • Methods: {', '.join(plan['methods'])} | Device: {plan['device']} "
        f"| CPU threads: {plan['threads']}"
    )
    console.print(f"   • Results: {directory}", markup=False)
    console.print(
        f"   • Resume: uv run python scripts/run_local_matrix.py --provider decisio "
        f"--resume '{directory}'",
        markup=False,
    )
    if plan["dataset"] == "public":
        console.print(
            "[dim]BANKING77: semantic scores 77 candidates per case; warmup is excluded. "
            "ETA becomes available after measured cases finish.[/]"
        )
    table = Table(title="Benchmark Summary")
    for name in ("Model", "Method", "Cases", "Accuracy", "Macro-F1", "p50", "p95"):
        table.add_column(name)
    exit_code = 0
    completed_outputs = []
    try:
        for index, model in enumerate(plan["models"], 1):
            console.rule(f"MODEL [{index}/{len(plan['models'])}]: {model}")
            output = directory if single else directory / model
            command = worker_command(
                plan,
                Path(registry[model]["path"]).expanduser(),
                output,
                resume=bool(args.resume and output.exists()),
            )
            display = RunDisplay(console, model, args.progress)
            code = run_worker(command, display)
            if code:
                console.print(f"[red]✗ Failed {model} (exit {code}); artifacts: {output}[/]")
                exit_code = 1
                continue
            completed_outputs.append((model, output))
            for method, summary in display.summaries.items():
                table.add_row(
                    model,
                    method,
                    str(summary["cases"]),
                    f"{summary['accuracy']:.1%}",
                    f"{summary['macro_f1']:.3f}",
                    f"{summary['latency_p50_ms']:.0f}ms",
                    f"{summary['latency_p95_ms']:.0f}ms",
                )
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Interrupted. Completed cases are saved; use the resume command above.[/]"
        )
        return 130
    console.print(table)
    if completed_outputs:
        imported = publish_decisio_results(
            directory,
            completed_outputs,
            output_csv=ROOT / "results/raw/local_results.csv",
            report_html=ROOT / "results/local_report.html",
        )
        console.print(f"[green]✓ Published {imported} Decisio rows to the dashboard[/]")
    console.print(f"Results: {directory}", markup=False)
    return exit_code
