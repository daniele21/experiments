"""progress.py.

Live progress bar and case-by-case evaluation visualizer using Rich.
Provides real-time feedback for benchmark evaluations across all providers (Jev, local Korgis, OpenAI, MiniCPM).
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from jev_bench.models import BenchmarkCase, QuestionSpec
from jev_bench.providers.base import DecisionProvider

# Global console instance
_console: Console | None = None


def get_console() -> Console:
    """Return a shared Rich Console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def should_show_progress(override: bool | None = None) -> bool:
    """Determine whether progress bar should be displayed.
    
    Respects explicit parameter override, terminal interactive state, and
    environment variable BENCHMARK_NO_PROGRESS.
    """
    if override is not None:
        return override
    if os.getenv("BENCHMARK_NO_PROGRESS", "0").lower() in {"1", "true", "yes"}:
        return False
    return sys.stdout.isatty()


def run_cases_with_progress(
    experiment: str,
    provider: DecisionProvider,
    cases: Sequence[BenchmarkCase],
    questions: Sequence[QuestionSpec],
    model_name: str | None = None,
    console: Console | None = None,
    show_progress: bool | None = None,
    row_builder: Callable[..., list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Execute benchmark cases while displaying a live progress bar and per-case feedback.

    Args:
        experiment: Experiment identifier (e.g., '01-routing', '01-routing-public').
        provider: The DecisionProvider instance evaluating each case.
        cases: Sequence of BenchmarkCase objects to evaluate.
        questions: Sequence of QuestionSpec questions to ask.
        model_name: Optional explicit model label; inferred from provider if omitted.
        console: Optional Rich Console instance.
        show_progress: Whether to show the visual progress; defaults to interactive check.
        row_builder: Function converting evaluate results to list of dict rows.

    Returns:
        Aggregated list of result row dicts.
    """
    if row_builder is None:
        from jev_bench.runner import _rows_for_case
        row_builder = _rows_for_case

    c = console or get_console()
    active_progress = should_show_progress(show_progress)
    resolved_model = model_name or getattr(provider, "model", None) or getattr(provider, "name", "unknown")

    total = len(cases)
    rows: list[dict[str, Any]] = []
    if total == 0:
        return rows

    correct_count = 0
    valid_count = 0
    latencies: list[float] = []
    started_at = time.perf_counter()

    if not active_progress:
        # Silent fallback for non-interactive / disabled mode
        for case in cases:
            result = provider.evaluate(case.state, questions)
            case_rows = row_builder(experiment, case, questions, result, primary=True)
            rows.extend(case_rows)
        return rows

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.fields[model]}[/]"),
        TextColumn("[bold yellow]{task.fields[exp]}[/]"),
        BarColumn(bar_width=25),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("[dim]({task.fields[status]})[/dim]"),
        console=c,
        transient=False,
    ) as progress:
        task = progress.add_task(
            "run",
            total=total,
            model=resolved_model,
            exp=experiment,
            status="initializing...",
        )

        for idx, case in enumerate(cases, start=1):
            result = provider.evaluate(case.state, questions)
            case_rows = row_builder(experiment, case, questions, result, primary=True)
            rows.extend(case_rows)

            lat = float(result.latency_ms) if result.latency_ms is not None else 0.0
            latencies.append(lat)

            is_valid = bool(result.valid)
            is_correct = any(bool(r.get("correct")) for r in case_rows)

            if is_valid:
                valid_count += 1
            if is_correct:
                correct_count += 1

            actual_val = case_rows[0].get("actual") if case_rows else None
            exp_val = case_rows[0].get("expected") if case_rows else None

            if is_correct:
                badge = f"[bold green]✓[/bold green] [green]correct[/green] (ans: [bold]{actual_val}[/bold])"
            elif is_valid:
                badge = f"[bold red]✗[/bold red] [yellow]mismatch[/yellow] (got: [bold]{actual_val}[/bold], exp: [bold]{exp_val}[/bold])"
            else:
                badge = f"[bold red]✗ invalid[/bold red] ({result.error})"

            progress.console.print(
                f"  [{idx:>3}/{total}] {badge} • [dim]{case.case_id}[/dim] • [cyan]{lat:.0f}ms[/cyan]"
            )

            acc = (correct_count / idx) * 100.0
            progress.update(
                task,
                advance=1,
                status=f"acc: {acc:.1f}% | lat: {lat:.0f}ms",
            )

    elapsed = time.perf_counter() - started_at
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    final_acc = (correct_count / total) * 100.0 if total > 0 else 0.0

    c.print(
        f"\n[bold green]✓ Done {resolved_model}[/] on [bold yellow]{experiment}[/] in [cyan]{elapsed:.1f}s[/] "
        f"| Acc: [bold]{final_acc:.1f}%[/] | Valid: [bold]{valid_count}/{total}[/] | Latency: [cyan]{avg_lat:.0f}ms[/]\n"
    )

    return rows
