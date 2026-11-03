from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import typer

from redact_bench.cloud_suite import prepare_cloud_reference, run_cloud_reference
from redact_bench.dataset_audit import audit_cases
from redact_bench.datasets import load_dataset
from redact_bench.document_fixtures import generate_pdf_fixtures
from redact_bench.e3c import download_e3c, prepare_e3c
from redact_bench.medical_datasets import fetch_asq, prepare_asq, prepare_meddocan, prepare_pharmaer
from redact_bench.clinical_gold import prepare_spaccc, prepare_e3c_clinical
from redact_bench.document_runner import run_document_compare
from redact_bench.documents import load_document_manifest
from redact_bench.progress import TerminalProgress
from redact_bench.preflight import run_model_preflight
from redact_bench.profiles import load_profile_snapshot
from redact_bench.provider import (
    DEFAULT_MODELS,
    KorgisController,
    KorgisRedactProvider,
    KorgisUnavailableError,
)
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


@app.command("prepare-e3c")
def prepare_e3c_command(
    source_dir: Path = typer.Option(
        ROOT / "data/cache/e3c-source",
        "--source-dir",
        help="Local E3C v2.0.0 checkout; used as-is unless --download is set.",
    ),
    output_dir: Path = typer.Option(
        ROOT / "data/cache/e3c-it-v2",
        "--output-dir",
        help="Local ignored cache for both generated E3C benchmark tracks.",
    ),
    download: bool = typer.Option(
        False,
        "--download",
        help="Download the upstream E3C tag using a shallow sparse Git checkout.",
    ),
) -> None:
    """Prepare the 50 official Italian test cases without publishing upstream text."""
    try:
        if download:
            download_e3c(source_dir)
        if not source_dir.is_dir():
            raise FileNotFoundError(
                f"No E3C checkout at {source_dir}; pass --download or --source-dir."
            )
        manifest = prepare_e3c(source_dir, output_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        typer.echo(f"ERROR: E3C preparation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"E3C {manifest['source_tag']}: {manifest['official_test_documents']} test "
        f"documents, {manifest['synthetic_pii']['entities_per_document']} "
        f"injected PII types per case"
    )
    typer.echo(f"Clinical context (unscored): {output_dir / 'clinical_context.jsonl'}")
    typer.echo(f"Targeted PII recall/leakage: {output_dir / 'synthetic_pii.jsonl'}")
    typer.echo(f"Provenance: {output_dir / 'manifest.json'}")
    typer.echo("Run: uv run redact-bench suite --config config/suite-e3c.yaml")


@app.command("prepare-spaccc")
def prepare_spaccc_command(
    annotations: Path = typer.Option(
        ROOT / "data/cache/medical-sources/spaccc/annotations/data/test-00000-of-00001.parquet",
        "--annotations", help="Official IEETA SPACCC-Spanish-NER TEST-only Parquet.",
    ),
    documents: Path = typer.Option(
        ROOT / "data/cache/medical-sources/spaccc/documents/data/train-00000-of-00001.parquet",
        "--documents", help="IEETA SPACCC-documents all original texts (train-named repository split).",
    ),
    limit: int = typer.Option(200, "--limit", min=1),
) -> None:
    """Join public clinical gold spans to original texts with strict exact offsets."""
    output = ROOT / "data/cache/spaccc-clinical-gold-v1"
    try:
        summary = prepare_spaccc(annotations, documents, output, limit=limit)
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(f"ERROR: SPACCC preparation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"SPACCC clinical gold: {summary['cases']} documents / {summary['gold_spans']} spans")
    typer.echo(f"Manifest: {output / 'manifest.json'}")
    typer.echo("Run: uv run redact-bench suite --config config/suite-spaccc-clinical.yaml")


@app.command("prepare-e3c-clinical")
def prepare_e3c_clinical_command(
    source_dir: Path = typer.Option(
        ROOT / "data/cache/e3c-source", "--source-dir",
        help="Existing pinned E3C v2.0.0 checkout from prepare-e3c --download.",
    ),
) -> None:
    """Import independently annotated Italian E3C clinical entities (no PII gold)."""
    output = ROOT / "data/cache/e3c-it-clinical-gold-v1"
    try:
        summary = prepare_e3c_clinical(source_dir, output)
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(f"ERROR: E3C clinical preparation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"E3C clinical gold: {summary['cases']} documents / {summary['gold_spans']} spans")
    typer.echo(f"Manifest: {output / 'manifest.json'}")
    typer.echo("Run: uv run redact-bench suite --config config/suite-e3c-clinical.yaml")


@app.command("prepare-medical")
def prepare_medical_command(
    dataset: str = typer.Option(..., "--dataset", help="asq-phi | meddocan | pharmaer"),
    source: Path | None = typer.Option(
        None, "--source", help="ASQ .txt, extracted MEDDOCAN root or PharmaER Gold test parquet/JSONL."
    ),
    download: bool = typer.Option(
        False, "--download", help="Fetch pinned ASQ-PHI ONLY (no other automatic downloads)."
    ),
    positives: int = typer.Option(160, "--positives", min=0),
    negatives: int = typer.Option(40, "--negatives", min=0),
    limit: int = typer.Option(40, "--limit", min=1),
) -> None:
    """Prepare locally scored medical benchmark subsets with strict gold offsets."""
    directory = {
        "asq-phi": "asq-phi-v1",
        "meddocan": "meddocan-test-v1",
        "pharmaer": "pharmaer-it-gold-test-v03",
    }.get(dataset)
    if directory is None:
        typer.echo("ERROR: expected --dataset asq-phi, meddocan or pharmaer", err=True)
        raise typer.Exit(code=2)
    output = ROOT / "data/cache" / directory
    if download and dataset != "asq-phi":
        typer.echo("ERROR: --download supported only for ASQ-PHI", err=True)
        raise typer.Exit(code=2)
    try:
        if dataset == "asq-phi":
            source_path = source or ROOT / "data/cache/medical-sources/asq-phi.txt"
            if download:
                fetch_asq(source_path)
            manifest = prepare_asq(source_path, output, positives=positives, negatives=negatives)
        elif dataset == "meddocan":
            source_path = source or ROOT / "data/cache/medical-sources/meddocan"
            manifest = prepare_meddocan(source_path, output, limit=limit)
        else:
            if source is None:
                raise ValueError("PharmaER requires --source pointing to GOLD test .parquet or .jsonl")
            manifest = prepare_pharmaer(source, output)
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(f"ERROR: medical preparation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"{manifest['dataset']} ({manifest['task']}): "
        f"{manifest['cases']} cases / {manifest['gold_count']} gold spans"
    )
    typer.echo(f"Dataset: {output / 'cases.jsonl'}")
    typer.echo(f"Provenance and limitations: {output / 'manifest.json'}")
    typer.echo(f"Run: uv run redact-bench suite --config config/suite-{dataset}.yaml")


@app.command("check-data")
def check_data(
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
) -> None:
    cases = load_dataset(dataset)
    typer.echo(f"{len(cases)} cases OK")


@app.command("audit-data")
def audit_data(
    dataset: Path = typer.Option(ROOT / "data/realistic"),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
) -> None:
    """Audit dataset balance, taxonomy coverage, semantic families and review state."""
    cases = load_dataset(dataset)
    snapshot = load_profile_snapshot(profiles)
    typer.echo(json.dumps(audit_cases(cases, snapshot), indent=2, ensure_ascii=False))


@app.command("preflight")
def preflight(
    models: str = typer.Option(",".join(DEFAULT_MODELS)),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
) -> None:
    """Verify each model can satisfy the RedactGuard inference contract."""
    selected = [item.strip() for item in models.split(",") if item.strip()]
    controller = KorgisController()
    try:
        controller.health()
        for model in selected:
            controller.activate(model)
            result = run_model_preflight(
                KorgisRedactProvider(model, str(profiles))
            )
            status = "PASS" if result["passed"] else "FAIL"
            typer.echo(
                f"{status} {model}: {result['status']} "
                f"resolved={result['resolved_item_count']} "
                f"raw={result['raw_item_count']} "
                f"finish={result['finish_reason'] or '—'}"
            )
            if result.get("error"):
                typer.echo(f"  {result['error']}", err=True)
    except KorgisUnavailableError as exc:
        _exit_korgis_unavailable(exc)


@app.command("compare")
def compare(
    models: str = typer.Option(",".join(DEFAULT_MODELS)),
    dataset: Path = typer.Option(ROOT / "data/smoke/cases.jsonl"),
    profiles: Path = typer.Option(ROOT / "config/profiles.yaml"),
    results_dir: Path = typer.Option(ROOT / "results"),
    warmups: int = typer.Option(1, min=0),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help="Show live model/case progress on stderr.",
    ),
    preflight: bool = typer.Option(
        True,
        "--preflight/--no-preflight",
        help="Gate model-quality scoring on a tiny structured-output preflight.",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help="Per-segment timeout in seconds (default: 360s or config).",
    ),
    chunk_max_chars: int | None = typer.Option(
        None,
        "--chunk-max-chars",
        help="Maximum characters per segment chunk.",
    ),
    adaptive_subdivision: bool = typer.Option(
        True,
        "--adaptive-subdivision/--no-adaptive-subdivision",
        help="Adaptively subdivide dense segments on failure.",
    ),
    cases: str | None = typer.Option(
        None,
        "--cases",
        "--case-ids",
        help="Optional comma-separated list of case IDs/filenames to evaluate (e.g. tabella_piccola.xlsx,contratto.doc).",
    ),
) -> None:
    selected = [item.strip() for item in models.split(",") if item.strip()]
    selected_cases = (
        [item.strip() for item in cases.split(",") if item.strip()]
        if cases
        else None
    )
    try:
        output = run_compare(
            models=selected,
            dataset_path=str(dataset),
            profiles_path=str(profiles),
            results_dir=str(results_dir),
            warmups=warmups,
            progress=TerminalProgress() if progress else None,
            preflight=preflight,
            timeout=timeout,
            chunk_max_chars=chunk_max_chars,
            adaptive_subdivision=adaptive_subdivision,
            case_ids=selected_cases,
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
    preflight: bool = typer.Option(
        True,
        "--preflight/--no-preflight",
        help="Require the model to satisfy the structured-output contract first.",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help="Per-segment timeout in seconds (default: 360s or config).",
    ),
    chunk_max_chars: int | None = typer.Option(
        None,
        "--chunk-max-chars",
        help="Maximum characters per segment chunk.",
    ),
    adaptive_subdivision: bool = typer.Option(
        True,
        "--adaptive-subdivision/--no-adaptive-subdivision",
        help="Adaptively subdivide dense segments on failure.",
    ),
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
            preflight=preflight,
            timeout=timeout,
            chunk_max_chars=chunk_max_chars,
            adaptive_subdivision=adaptive_subdivision,
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



@app.command("cloud-reference")
def cloud_reference(
    dataset: str = typer.Option(
        "healthcare", help="Frozen synthetic fixture: healthcare, ambiguous or challenge."
    ),
    model: str = typer.Option("gpt-6-luna", help="Approved API model ID."),
    max_cases: int | None = typer.Option(
        None, min=1, help="Smoke-test the first N cases; smoke results are excluded from leaderboards."
    ),
    confirm_cloud: bool = typer.Option(
        False, "--confirm-cloud", help="Explicitly permit sending synthetic text to the OpenAI API."
    ),
    check_only: bool = typer.Option(
        False, "--check-only", help="Validate dataset and print the plan without making API calls."
    ),
) -> None:
    """Run a separately identified GPT-6 Luna cloud reference, scored like local GGUF."""
    try:
        plan = prepare_cloud_reference(
            experiment_root=ROOT, dataset=dataset, model=model, max_cases=max_cases,
        )
        typer.echo(
            f"Cloud reference: {model} | {dataset} | "
            f"{len(plan['cases'])}/{plan['total_cases']} synthetic cases "
            f"| scope={plan['scope']}"
        )
        if check_only:
            typer.echo("Check only. No network requests, credentials or charges.")
            return
        if not confirm_cloud:
            typer.echo(
                "ERROR: --confirm-cloud required. Dataset text and prompts leave this Mac. "
                "API billing is separate from ChatGPT.",
                err=True,
            )
            raise typer.Exit(code=2)
        output = run_cloud_reference(
            experiment_root=ROOT, dataset=dataset, model=model,
            max_cases=max_cases, confirm_cloud=confirm_cloud,
        )
        typer.echo(f"Suite: {output}")
        typer.echo("UI: uv run redact-bench ui  -> /client/capabilities")
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc


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
    suite_status = json.loads((output / "suite.json").read_text(encoding="utf-8"))
    if suite_status.get("quality_only"):
        typer.echo(f"quality artifacts: {output / 'quality'}")
        typer.echo("Interactive dashboard: uv run redact-bench ui")
    else:
        typer.echo(f"dashboard: {ROOT / 'results/dashboard.html'}")


@app.command("probe-quality")
def probe_quality(
    models: str = typer.Option(..., "--models", help="Comma-separated model IDs."),
    cases: str = typer.Option(..., "--cases", help="Comma-separated document IDs/filenames."),
    config: Path = typer.Option(ROOT / "config/suite.yaml"),
    korgis_repo: Path | None = typer.Option(None, "--korgis-repo"),
    chunk_max_chars: int | None = typer.Option(None, "--chunk-max-chars", min=512),
) -> None:
    """Run only selected failing documents with managed Korgis, no latency repetitions."""
    from redact_bench.quality_probe import run_quality_probe

    try:
        output = run_quality_probe(
            config_path=config,
            root=ROOT,
            models=[v.strip() for v in models.split(",") if v.strip()],
            case_ids=[v.strip() for v in cases.split(",") if v.strip()],
            korgis_repo=korgis_repo,
            chunk_max_chars=chunk_max_chars,
        )
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"probe: {output}")
    typer.echo(f"raw quality evidence: {output}/<model>/<run-id>/*.jsonl")


@app.command("audit-suite")
def audit_suite(
    suite_dir: Path = typer.Argument(..., help="Completed results/suites/<suite-id> directory."),
) -> None:
    """Audit raw suite evidence (micro/macro/family recall, cache hits, JSON failures)."""
    from redact_bench.suite_audit import write_suite_audit

    try:
        json_path, markdown_path = write_suite_audit(suite_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"audit JSON: {json_path}")
    typer.echo(f"audit Markdown: {markdown_path}")


@app.command("dashboard")
def dashboard(
    history: Path = typer.Option(ROOT / "results/history.jsonl"),
    output: Path = typer.Option(ROOT / "results/dashboard.html"),
) -> None:
    """Rebuild the append-only benchmark history dashboard."""
    path = write_history_dashboard(history, output)
    typer.echo(str(path))


def _write_ui_taxonomy_snapshot(ui_dir: Path) -> Path:
    """Expose the pinned RedactGuard profile taxonomy to the local UI."""
    payload = load_profile_snapshot(ROOT / "config/profiles.yaml")
    public_dir = ui_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    output = public_dir / "pii-taxonomy.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", help="Host for the local React dashboard."),
    port: int = typer.Option(5173, min=1, max=65535, help="Port for the local React dashboard."),
) -> None:
    """Launch the React dashboard that reads benchmark results dynamically."""
    ui_dir = ROOT / "ui"
    package_json = ui_dir / "package.json"
    if not package_json.exists():
        typer.echo(f"ERROR: UI package not found at {ui_dir}", err=True)
        raise typer.Exit(code=2)
    if shutil.which("npm") is None:
        typer.echo("ERROR: npm is required to run the React dashboard.", err=True)
        raise typer.Exit(code=2)
    if not (ui_dir / "node_modules").exists():
        typer.echo("UI dependencies are not installed.", err=True)
        typer.echo("Run once:", err=True)
        typer.echo("  npm --prefix ui install", err=True)
        raise typer.Exit(code=2)

    taxonomy_path = _write_ui_taxonomy_snapshot(ui_dir)
    typer.echo(f"taxonomy: {taxonomy_path}")
    typer.echo(f"dashboard: http://{host}:{port}")
    try:
        completed = subprocess.run(
            ["npm", "run", "dev", "--", "--host", host, "--port", str(port)],
            cwd=ui_dir,
            check=False,
        )
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode)
