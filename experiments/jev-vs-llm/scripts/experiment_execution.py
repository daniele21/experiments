"""Shared benchmark experiment execution with per-case progress output."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
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

from jev_bench.benchmark_data import (
    DEFAULT_CACHE,
    balanced_banking77_cases,
    banking77_question,
    calibration_public_cases,
)
from jev_bench.cli import PUBLIC_PROFILES
from jev_bench.datasets import (
    calibration_cases,
    expense_cases,
    expense_questions,
    routing_cases,
    routing_questions,
    support_cases,
    support_questions,
)
from jev_bench.models import BenchmarkCase, QuestionSpec
from jev_bench.providers.base import DecisionProvider
from jev_bench.runner import (
    _expense_action,
    _rows_for_case,
    _support_action,
    run_scaling,
    run_workflow,
)

console = Console()


def run_cases_with_progress(
    experiment: str,
    provider: DecisionProvider,
    cases: Sequence[BenchmarkCase],
    questions: Sequence[QuestionSpec],
    model_name: str,
) -> list[dict]:
    """Execute benchmark cases with the same live detail used by local runs."""
    rows: list[dict] = []
    total = len(cases)
    correct_count = 0
    valid_count = 0

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
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            "run",
            total=total,
            model=model_name,
            exp=experiment,
            status="initializing...",
        )

        for idx, case in enumerate(cases, start=1):
            result = provider.evaluate(case.state, questions)
            case_rows = _rows_for_case(experiment, case, questions, result, primary=True)
            rows.extend(case_rows)

            is_valid = bool(result.valid)
            is_correct = any(bool(row.get("correct")) for row in case_rows)
            if is_valid:
                valid_count += 1
            if is_correct:
                correct_count += 1

            actual = case_rows[0].get("actual") if case_rows else None
            expected = case_rows[0].get("expected") if case_rows else None
            if is_correct:
                badge = f"[bold green]✓[/] [green]correct[/] (ans: [bold]{actual}[/])"
            elif is_valid:
                badge = (
                    f"[bold red]✗[/] [yellow]mismatch[/] "
                    f"(got: [bold]{actual}[/], exp: [bold]{expected}[/])"
                )
            else:
                badge = f"[bold red]✗ invalid[/] ({result.error})"

            progress.console.print(
                f"  [{idx:>3}/{total}] {badge} • [dim]{case.case_id}[/] "
                f"• [cyan]{result.latency_ms:.0f}ms[/]"
            )
            accuracy = correct_count / idx * 100
            progress.update(
                task,
                advance=1,
                status=(
                    f"acc: {accuracy:.1f}% | valid: {valid_count}/{idx} "
                    f"| lat: {result.latency_ms:.0f}ms"
                ),
            )

    return rows


def run_single_experiment(
    *,
    exp_name: str,
    provider: DecisionProvider,
    model_name: str,
    dataset: str,
    profile: str,
    cache_dir: Path = DEFAULT_CACHE,
    seed: int = 42,
) -> pd.DataFrame:
    """Run one smoke/public experiment for any DecisionProvider."""
    clean_exp = exp_name.strip().lower().replace("_", "-")

    if dataset == "public":
        sizes = PUBLIC_PROFILES[profile]
        if clean_exp == "routing":
            cases = balanced_banking77_cases(
                cache_dir,
                max_cases=sizes["routing"],
                seed=seed,
                experiment="01-routing-public",
            )
            questions = [banking77_question(cache_dir, include_other=False)]
            return pd.DataFrame(
                run_cases_with_progress(
                    "01-routing-public",
                    provider,
                    cases,
                    questions,
                    model_name,
                )
            )
        if clean_exp == "calibration":
            cases = calibration_public_cases(
                cache_dir,
                in_scope_cases=sizes["in_scope"],
                oos_cases=sizes["oos"],
                seed=seed,
            )
            questions = [banking77_question(cache_dir, include_other=True)]
            return pd.DataFrame(
                run_cases_with_progress(
                    "02-calibration-public",
                    provider,
                    cases,
                    questions,
                    model_name,
                )
            )
        raise ValueError(
            "Public dataset tier supports only routing and calibration; "
            f"got {clean_exp!r}."
        )

    if clean_exp == "routing":
        rows = run_cases_with_progress(
            "01-routing",
            provider,
            routing_cases(),
            routing_questions(),
            model_name,
        )
    elif clean_exp == "calibration":
        rows = run_cases_with_progress(
            "02-calibration",
            provider,
            calibration_cases(),
            routing_questions(),
            model_name,
        )
    elif clean_exp == "scaling":
        rows = run_scaling(provider)
    elif clean_exp == "workflow":
        rows = run_workflow(
            "04-workflow",
            provider,
            expense_cases(),
            expense_questions(),
            _expense_action,
        )
    elif clean_exp == "agent":
        rows = run_workflow(
            "05-hybrid-agent",
            provider,
            support_cases(),
            support_questions(),
            _support_action,
        )
    else:
        raise ValueError(f"Unknown experiment {clean_exp!r}.")

    return pd.DataFrame(rows)
