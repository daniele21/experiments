from __future__ import annotations

from pathlib import Path

import typer

from redact_bench.datasets import load_dataset
from redact_bench.document_fixtures import generate_pdf_fixtures
from redact_bench.document_runner import run_document_compare
from redact_bench.documents import load_document_manifest
from redact_bench.provider import DEFAULT_MODELS, KorgisController
from redact_bench.realistic_dataset import validate_realistic_dataset
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
    output = run_document_compare(
        models=selected,
        manifest_path=str(manifest),
        profiles_path=str(profiles),
        fixtures_dir=str(fixtures_dir),
        results_dir=str(results_dir),
        generate_fixtures=generate_fixtures,
        warmups=warmups,
    )
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
