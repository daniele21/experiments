from __future__ import annotations

from pathlib import Path

import typer

from redact_bench.datasets import load_dataset
from redact_bench.document_fixtures import generate_pdf_fixtures
from redact_bench.document_runner import run_document_compare
from redact_bench.documents import load_document_manifest
from redact_bench.provider import DEFAULT_MODELS, KorgisController, KorgisUnavailableError
from redact_bench.realistic_dataset import validate_realistic_dataset
from redact_bench.runner import run_compare, run_latency
from redact_bench.history_dashboard import write_history_dashboard
from redact_bench.suite import run_managed_suite

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]


def _exit_korgis_unavailable(exc: KorgisUnavailableError) -> None:
    typer.echo(f"ERROR: {exc}", err=True)
    typer.echo("", err=True)
    typer.echo("For the managed benchmark flow, run:", err=True)
    typer.echo("  uv run redact-bench suite", err=True)
    typer.echo("", err=True)
    typer.echo("For manual Korgis operation, start it from the Korgis repository:", err=True)
    typer.echo(
        "  uv run --frozen local-llm serve "
        "--model nemotron-nano-4b --enable-admin-api --no-download",
        err=True,
    )
    typer.echo("", err=True)
    typer.echo("Then verify it from this experiment:", err=True)
    typer.echo("  uv run redact-bench check-korgis", err=True)
    typer.echo("", err=True)
    typer.echo(
        "If Korgis uses another address, set KORGIS_BASE_URL, e.g. "
        "http://127.0.0.1:1235/v1",
        err=True,
    )
    raise typer.Exit(code=2)


@app.command("check-korgis")
def check_korgis() -> None:
    """Verify the external current Korgis server and print available registry evidence."""
    controller = KorgisController()
    try:
        health = controller.health()
        registry = controller.registry()
        identity = controller.identity()
    except KorgisUnavailableError as exc:
        _exit_korgis_unavailable(exc)
    typer.echo(f"health: {health}")
    typer.echo(f"registry: {registry}")
    typer.echo(f"identity: {identity}")


@app.command("check-data")
def check_data(
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
) -> None:
    cases = load_dataset(dataset)
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
    try:
        output = run_compare(
            models=selected,
            dataset_path=str(dataset),
            profiles_path=str(profiles),
            results_dir=str(results_dir),
            warmups=warmups,
        )
    except KorgisUnavailableError as exc:
        _exit_korgis_unavailable(exc)
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
    try:
        output = run_latency(
            models=selected,
            dataset_path=str(dataset),
            profiles_path=str(profiles),
            results_dir=str(results_dir),
            warmups=warmups,
            repeats=repeats,
            case_ids=latency_cases,
        )
    except KorgisUnavailableError as exc:
        _exit_korgis_unavailable(exc)
    typer.echo(str(output))


@app.command("check-documents")
def check_documents(
    manifest: Path = typer.Option(ROOT / "data/documents/manifest.jsonl"),
) -> None:
    """Validate the committed document manifest without loading Docling."""
    documents = load_document_manifest(manifest)
    pages = sum(len(document.pages) for document in documents)
    entities = sum(len(page.gold) for document in documents for page in document.pages)
    typer.echo(f"{len(documents)} documents / {pages} pages / {entities} gold entities OK")


@app.command("make-document-fixtures")
def make_document_fixtures(
    manifest: Path = typer.Option(ROOT / "data/documents/manifest.jsonl"),
    fixtures_dir: Path = typer.Option(ROOT / "data/documents/generated"),
) -> None:
    """Generate deterministic synthetic PDF fixtures from the committed source manifest."""
    documents = load_document_manifest(manifest)
    paths = generate_pdf_fixtures(documents, fixtures_dir)
    for path in paths:
        typer.echo(str(path))


@app.command("documents")
def documents(
    models: str = typer.Option(",".join(DEFAULT_MODELS)),
    manifest: Path = typer.Option(ROOT / "data/documents/manifest.jsonl"),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
    fixtures_dir: Path = typer.Option(ROOT / "data/documents/generated"),
    results_dir: Path = typer.Option(ROOT / "results"),
    warmups: int = typer.Option(1, min=0),
    generate_fixtures: bool = typer.Option(
        True,
        "--generate-fixtures/--no-generate-fixtures",
    ),
) -> None:
    """Run PDF -> Docling -> Korgis -> RedactGuard post-processing end to end."""
    selected = [item.strip() for item in models.split(",") if item.strip()]
    try:
        output = run_document_compare(
            models=selected,
            manifest_path=str(manifest),
            profiles_path=str(profiles),
            fixtures_dir=str(fixtures_dir),
            results_dir=str(results_dir),
            generate_fixtures=generate_fixtures,
            warmups=warmups,
        )
    except KorgisUnavailableError as exc:
        _exit_korgis_unavailable(exc)
    typer.echo(str(output))



@app.command("check-realistic-dataset")
def check_realistic_dataset(
    dataset_dir: Path = typer.Option(ROOT / "data/realistic"),
    require_originals: bool = typer.Option(
        False,
        "--require-originals/--no-require-originals",
    ),
) -> None:
    """Validate a downloaded realistic dataset, its hashes and every gold span."""
    summary = validate_realistic_dataset(
        dataset_dir,
        require_originals=require_originals,
    )
    typer.echo(
        f"{summary['dataset_id']}: {summary['documents']} documents / "
        f"{summary['spans']} gold spans OK"
    )
    typer.echo(f"by_type: {summary['by_type']}")



@app.command("suite")
def suite(
    config: Path = typer.Option(ROOT / "config/suite.yaml"),
    korgis_repo: Path | None = typer.Option(
        None,
        help="Path to the Korgis repository. Auto-detected when omitted.",
    ),
    models: str | None = typer.Option(
        None,
        help="Optional comma-separated model override. Defaults to config/suite.yaml.",
    ),
    ensure_models: bool | None = typer.Option(
        None,
        "--ensure-models/--no-ensure-models",
        help="Override whether Korgis should ensure model artifacts before the run.",
    ),
) -> None:
    """Run the managed Korgis -> quality -> latency -> history -> dashboard workflow."""
    selected = None
    if models:
        selected = [item.strip() for item in models.split(",") if item.strip()]
    try:
        output = run_managed_suite(
            config_path=config,
            experiment_root=ROOT,
            korgis_repo=korgis_repo,
            model_override=selected,
            ensure_models_override=ensure_models,
        )
    except (ValueError, RuntimeError, TimeoutError, FileNotFoundError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"suite: {output}")
    typer.echo(f"dashboard: {ROOT / 'results/dashboard.html'}")


@app.command("dashboard")
def dashboard(
    history: Path = typer.Option(ROOT / "results/history.jsonl"),
    output: Path = typer.Option(ROOT / "results/dashboard.html"),
) -> None:
    """Rebuild the append-only benchmark history dashboard."""
    path = write_history_dashboard(history, output)
    typer.echo(str(path))
