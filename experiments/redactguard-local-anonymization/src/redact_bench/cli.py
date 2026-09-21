from __future__ import annotations

from pathlib import Path

import typer

from redact_bench.datasets import load_jsonl
from redact_bench.provider import DEFAULT_MODELS, KorgisController
from redact_bench.runner import run_compare, run_latency

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]


@app.command("check-korgis")
def check_korgis() -> None:
    """Verify the external current Korgis server and print available registry evidence."""
    controller = KorgisController()
    health = controller.health()
    registry = controller.registry()
    identity = controller.identity()
    typer.echo(f"health: {health}")
    typer.echo(f"registry: {registry}")
    typer.echo(f"identity: {identity}")


@app.command("check-data")
def check_data(
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
) -> None:
    cases = load_jsonl(dataset)
    typer.echo(f"{len(cases)} cases OK")


@app.command("compare")
def compare(
    models: str = typer.Option(",".join(DEFAULT_MODELS)),
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
    results_dir: Path = typer.Option(ROOT / "results"),
    warmups: int = typer.Option(1, min=0),
) -> None:
    selected = [item.strip() for item in models.split(",") if item.strip()]
    output = run_compare(
        models=selected,
        dataset_path=str(dataset),
        profiles_path=str(profiles),
        results_dir=str(results_dir),
        warmups=warmups,
    )
    typer.echo(str(output))


@app.command("latency")
def latency(
    models: str = typer.Option(",".join(DEFAULT_MODELS)),
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
    results_dir: Path = typer.Option(ROOT / "results"),
    warmups: int = typer.Option(5, min=0),
    repeats: int = typer.Option(30, min=1),
    case_ids: str = typer.Option("g01,g04,h05,f01,l02"),
) -> None:
    """Run a dedicated repeated latency suite without changing quality scoring."""
    selected = [item.strip() for item in models.split(",") if item.strip()]
    latency_cases = [item.strip() for item in case_ids.split(",") if item.strip()]
    output = run_latency(
        models=selected,
        dataset_path=str(dataset),
        profiles_path=str(profiles),
        results_dir=str(results_dir),
        warmups=warmups,
        repeats=repeats,
        case_ids=latency_cases,
    )
    typer.echo(str(output))
