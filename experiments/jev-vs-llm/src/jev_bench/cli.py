from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from jev_bench.benchmark_data import DEFAULT_CACHE, prepare_public_data
from jev_bench.providers.jev import JevProvider
from jev_bench.providers.openai import OpenAIMonolithicProvider, OpenAIProvider
from jev_bench.report import build_report
from jev_bench.runner import (
    append_results,
    run_all,
    run_monolithic_workflows,
    run_public_classification,
)

app = typer.Typer(no_args_is_help=True)
DEFAULT_RAW = Path("results/raw/results.csv")
DEFAULT_REPORT = Path("results/report.html")
PUBLIC_RAW = Path("results/raw/public_results.csv")
PUBLIC_REPORT = Path("results/public_report.html")

PUBLIC_PROFILES = {
    "quick": {"routing": 154, "in_scope": 100, "oos": 100},
    "standard": {"routing": 770, "in_scope": 500, "oos": 500},
    "full": {"routing": None, "in_scope": 1000, "oos": 1000},
}


def _tag_run(frame: pd.DataFrame, run_group: str, suite: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["run_id"] = str(uuid.uuid4())
    frame["run_group"] = run_group
    frame["suite"] = suite
    frame["run_timestamp_utc"] = datetime.now(UTC).isoformat()
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


def _decision_provider(provider: str):
    if provider == "jev":
        return JevProvider()
    if provider == "llm":
        return OpenAIProvider()
    raise typer.BadParameter("public classification supports jev or llm")


@app.command("prepare-data")
def prepare_data(
    cache_dir: Annotated[Path, typer.Option(help="Local dataset cache directory.")] = DEFAULT_CACHE,
) -> None:
    """Download canonical public datasets into the local gitignored cache."""
    paths = prepare_public_data(cache_dir)
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command()
def run(
    provider: Annotated[str, typer.Option(help="jev, llm, or llm-monolithic")],
    output: Annotated[Path, typer.Option()] = DEFAULT_RAW,
    scaling_repeats: Annotated[int, typer.Option(min=1)] = 5,
    run_group: Annotated[
        str | None, typer.Option(help="Shared ID for comparable runs.")
    ] = None,
) -> None:
    """Run the small smoke suite for one provider."""
    group = run_group or str(uuid.uuid4())
    frame = _tag_run(_execute(provider, scaling_repeats), group, "smoke")
    append_results(frame, output)
    typer.echo(f"Wrote {len(frame)} rows to {output} (run_group={group})")


@app.command()
def compare(
    output: Annotated[Path, typer.Option()] = DEFAULT_RAW,
    html: Annotated[Path, typer.Option()] = DEFAULT_REPORT,
    scaling_repeats: Annotated[int, typer.Option(min=1)] = 10,
) -> None:
    """Run the three smoke-suite arms under one comparison group."""
    group = str(uuid.uuid4())
    frames = []
    for provider in ["jev", "llm", "llm-monolithic"]:
        typer.echo(f"Running {provider}...")
        frames.append(_tag_run(_execute(provider, scaling_repeats), group, "smoke"))
    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"Dashboard: {html}")


@app.command("compare-public")
def compare_public(
    profile: Annotated[
        str, typer.Option(help="quick, standard, or full")
    ] = "standard",
    output: Annotated[Path, typer.Option()] = PUBLIC_RAW,
    html: Annotated[Path, typer.Option()] = PUBLIC_REPORT,
    cache_dir: Annotated[Path, typer.Option()] = DEFAULT_CACHE,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    """Run Jev vs decomposed LLM on BANKING77 + conservatively filtered CLINC150 OOS."""
    if profile not in PUBLIC_PROFILES:
        raise typer.BadParameter("profile must be quick, standard, or full")

    sizes = PUBLIC_PROFILES[profile]
    prepare_public_data(cache_dir)
    group = str(uuid.uuid4())
    frames = []
    for provider in ["jev", "llm"]:
        typer.echo(f"Running public {profile} benchmark: {provider}...")
        frame = run_public_classification(
            _decision_provider(provider),
            cache_dir=cache_dir,
            routing_max_cases=sizes["routing"],
            calibration_in_scope=sizes["in_scope"],
            calibration_oos=sizes["oos"],
            seed=seed,
        )
        frames.append(_tag_run(frame, group, f"public-{profile}"))

    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"Dashboard: {html}")


@app.command()
def report(
    input_csv: Annotated[Path, typer.Option()] = DEFAULT_RAW,
    output_html: Annotated[Path, typer.Option()] = DEFAULT_REPORT,
    run_group: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Build the interactive HTML dashboard from raw benchmark rows."""
    build_report(input_csv, output_html, run_group=run_group)
    typer.echo(f"Wrote {output_html}")


if __name__ == "__main__":
    app()
