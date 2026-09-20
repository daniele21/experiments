from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import typer

from jev_bench.providers.jev import JevProvider
from jev_bench.providers.openai import OpenAIMonolithicProvider, OpenAIProvider
from jev_bench.report import build_report
from jev_bench.runner import append_results, run_all, run_monolithic_workflows

app = typer.Typer(no_args_is_help=True)
DEFAULT_RAW = Path("results/raw/results.csv")
DEFAULT_REPORT = Path("results/report.html")


def _tag_run(frame: pd.DataFrame, run_group: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["run_id"] = str(uuid.uuid4())
    frame["run_group"] = run_group
    frame["run_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    frame["runner_location"] = os.getenv("BENCHMARK_LOCATION", "unspecified")
    return frame


def _execute(provider: str, scaling_repeats: int) -> pd.DataFrame:
    if provider == "jev":
        return run_all(JevProvider(), scaling_repeats=scaling_repeats)
    if provider == "llm":
        return run_all(OpenAIProvider(), scaling_repeats=scaling_repeats)
    if provider == "llm-monolithic":
        return run_monolithic_workflows(OpenAIMonolithicProvider())
    raise typer.BadParameter("provider must be jev, llm, or llm-monolithic")


@app.command()
def run(
    provider: str = typer.Option(..., help="jev, llm, or llm-monolithic"),
    output: Path = typer.Option(DEFAULT_RAW),
    scaling_repeats: int = typer.Option(5, min=1),
    run_group: str | None = typer.Option(None, help="Shared ID for comparable runs."),
) -> None:
    """Run the selected benchmark arm and append raw rows."""
    group = run_group or str(uuid.uuid4())
    frame = _tag_run(_execute(provider, scaling_repeats), group)
    append_results(frame, output)
    typer.echo(f"Wrote {len(frame)} rows to {output} (run_group={group})")


@app.command()
def compare(
    output: Path = typer.Option(DEFAULT_RAW),
    html: Path = typer.Option(DEFAULT_REPORT),
    scaling_repeats: int = typer.Option(10, min=1),
) -> None:
    """Run Jev, decomposed LLM, and monolithic LLM under one comparison group."""
    group = str(uuid.uuid4())
    frames = []
    for provider in ["jev", "llm", "llm-monolithic"]:
        typer.echo(f"Running {provider}...")
        frames.append(_tag_run(_execute(provider, scaling_repeats), group))
    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"Dashboard: {html}")


@app.command()
def report(
    input_csv: Path = typer.Option(DEFAULT_RAW),
    output_html: Path = typer.Option(DEFAULT_REPORT),
    run_group: str | None = typer.Option(None),
) -> None:
    """Build the interactive HTML dashboard from raw benchmark rows."""
    build_report(input_csv, output_html, run_group=run_group)
    typer.echo(f"Wrote {output_html}")


if __name__ == "__main__":
    app()
