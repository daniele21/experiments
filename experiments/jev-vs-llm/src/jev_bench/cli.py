from __future__ import annotations

from pathlib import Path

import typer

from jev_bench.providers.jev import JevProvider
from jev_bench.providers.openai import OpenAIProvider
from jev_bench.report import build_report
from jev_bench.runner import append_results, run_all

app = typer.Typer(no_args_is_help=True)
DEFAULT_RAW = Path("results/raw/results.csv")
DEFAULT_REPORT = Path("results/report.html")


@app.command()
def run(
    provider: str = typer.Option(..., help="jev or llm"),
    output: Path = typer.Option(DEFAULT_RAW),
    scaling_repeats: int = typer.Option(5, min=1),
) -> None:
    """Run all five experiments for one provider and append raw rows."""
    if provider == "jev":
        impl = JevProvider()
    elif provider == "llm":
        impl = OpenAIProvider()
    else:
        raise typer.BadParameter("provider must be 'jev' or 'llm'")
    frame = run_all(impl, scaling_repeats=scaling_repeats)
    append_results(frame, output)
    typer.echo(f"Wrote {len(frame)} rows to {output}")


@app.command()
def report(
    input_csv: Path = typer.Option(DEFAULT_RAW),
    output_html: Path = typer.Option(DEFAULT_REPORT),
) -> None:
    """Build the interactive HTML dashboard from raw benchmark rows."""
    build_report(input_csv, output_html)
    typer.echo(f"Wrote {output_html}")


@app.command("run-and-report")
def run_and_report(
    provider: str = typer.Option(..., help="jev or llm"),
    raw: Path = typer.Option(DEFAULT_RAW),
    html: Path = typer.Option(DEFAULT_REPORT),
    scaling_repeats: int = typer.Option(5, min=1),
) -> None:
    run(provider=provider, output=raw, scaling_repeats=scaling_repeats)
    build_report(raw, html)
    typer.echo(f"Dashboard: {html}")


if __name__ == "__main__":
    app()
