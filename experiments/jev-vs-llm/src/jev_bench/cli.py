from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from jev_bench.benchmark_data import DEFAULT_CACHE, prepare_public_data
from jev_bench.costs import pricing_metadata
from jev_bench.manifest import write_manifest
from jev_bench.providers.jev import JevProvider
from jev_bench.providers.korgis import (
    DEFAULT_KORGIS_MODELS,
    KorgisController,
    KorgisProvider,
    ensure_korgis_models_resident,
    managed_korgis_model_order,
)
from jev_bench.providers.openai import OpenAIMonolithicProvider, OpenAIProvider
from jev_bench.report import build_report
from jev_bench.runner import (
    append_results,
    run_all,
    run_experiment,
    run_monolithic_workflows,
    run_public_classification,
)

app = typer.Typer(no_args_is_help=True)
DEFAULT_RAW = Path("results/raw/results.csv")
DEFAULT_REPORT = Path("results/report.html")
PUBLIC_RAW = Path("results/raw/public_results.csv")
PUBLIC_REPORT = Path("results/public_report.html")
MANIFEST_DIR = Path("results/manifests")

DEFAULT_OPENAI_MODELS = [
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
]

PUBLIC_PROFILES = {
    "budget": {"routing": 77, "in_scope": 40, "oos": 40},
    "quick": {"routing": 154, "in_scope": 100, "oos": 100},
    "standard": {"routing": 770, "in_scope": 500, "oos": 500},
    "full": {"routing": None, "in_scope": None, "oos": None},
}


def _runner_location() -> str:
    return os.getenv("BENCHMARK_LOCATION", "unspecified")


def _model_matrix(value: str | None = None) -> list[str]:
    raw = value or os.getenv("OPENAI_MODELS", "")
    if raw.strip():
        models = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        models = DEFAULT_OPENAI_MODELS.copy()
    if not models:
        raise typer.BadParameter("At least one OpenAI model is required.")
    return list(dict.fromkeys(models))


def _local_model_matrix(value: str | None = None) -> list[str]:
    raw = value or os.getenv("KORGIS_MODELS", "")
    models = (
        [item.strip() for item in raw.split(",") if item.strip()]
        if raw.strip()
        else DEFAULT_KORGIS_MODELS.copy()
    )
    if not models:
        raise typer.BadParameter("At least one Korgis model is required.")
    return list(dict.fromkeys(models))


def _tag_run(frame: pd.DataFrame, run_group: str, suite: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["run_id"] = str(uuid.uuid4())
    frame["run_group"] = run_group
    frame["suite"] = suite
    frame["run_timestamp_utc"] = datetime.now(UTC).isoformat()
    frame["runner_location"] = _runner_location()
    return frame


def _resolved_models(frame: pd.DataFrame) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for provider, rows in frame.groupby("provider"):
        result[str(provider)] = sorted(rows["model"].dropna().astype(str).unique().tolist())
    return result


def _record_manifest(
    frame: pd.DataFrame,
    *,
    group: str,
    suite: str,
    parameters: dict,
    requested_openai_models: list[str] | None = None,
    requested_korgis_models: list[str] | None = None,
    korgis_identity: dict | None = None,
) -> Path:
    path = MANIFEST_DIR / f"{group}.json"
    dataset_revisions: dict[str, list[str]] = {}
    if {"dataset", "dataset_revision"}.issubset(frame.columns):
        valid = frame[frame["dataset"].notna() & frame["dataset_revision"].notna()]
        for dataset, rows in valid.groupby("dataset"):
            dataset_revisions[str(dataset)] = sorted(
                rows["dataset_revision"].astype(str).unique().tolist()
            )

    parameters = {
        **parameters,
        "dataset_revisions": dataset_revisions,
        "transport": {
            "max_retries": int(os.getenv("BENCHMARK_MAX_RETRIES", "0")),
            "timeout_seconds": float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60")),
        },
        "openai_reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "none"),
    }
    write_manifest(
        path,
        run_group=group,
        suite=suite,
        runner_location=_runner_location(),
        requested_models={
            "jev": os.getenv("JEV_MODEL", "jev-latest"),
            "openai": requested_openai_models or [os.getenv("OPENAI_MODEL", "")],
            "korgis": requested_korgis_models or [],
        },
        resolved_models=_resolved_models(frame),
        parameters={
            **parameters,
            "korgis_identity": korgis_identity or {},
        },
        pricing=pricing_metadata(),
    )
    return path


def _execute(provider: str, scaling_repeats: int) -> pd.DataFrame:
    if provider == "jev":
        return run_all(JevProvider(), scaling_repeats=scaling_repeats)
    if provider == "llm":
        return run_all(OpenAIProvider(), scaling_repeats=scaling_repeats)
    if provider == "llm-monolithic":
        return run_monolithic_workflows(OpenAIMonolithicProvider())
    raise typer.BadParameter("provider must be jev, llm, or llm-monolithic")


def _decision_provider(provider: str, model: str | None = None):
    if provider == "jev":
        return JevProvider()
    if provider == "llm":
        return OpenAIProvider(model=model)
    raise typer.BadParameter("public classification supports jev or llm")


def _run_korgis_public(
    *,
    models: list[str],
    profile: str,
    cache_dir: Path,
    seed: int,
    group: str,
    manage_runtime: bool,
    anchor_model: str,
) -> tuple[list[pd.DataFrame], dict]:
    sizes = PUBLIC_PROFILES[profile]
    controller = KorgisController()
    controller.health()
    identities: dict = {}
    frames: list[pd.DataFrame] = []

    if manage_runtime:
        controller.activate(anchor_model)
        order = managed_korgis_model_order(models, anchor_model)
    else:
        ensure_korgis_models_resident(controller, models)
        order = models

    for model in order:
        typer.echo(f"Running local Korgis benchmark: {model}...")
        if manage_runtime:
            controller.activate(model)
        try:
            frame = run_public_classification(
                KorgisProvider(model=model, seed=seed),
                cache_dir=cache_dir,
                routing_max_cases=sizes["routing"],
                calibration_in_scope=sizes["in_scope"],
                calibration_oos=sizes["oos"],
                seed=seed,
            )
            frames.append(_tag_run(frame, group, f"public-{profile}"))
            identities[model] = controller.model_identity(model)
        finally:
            if manage_runtime and model != anchor_model:
                controller.activate(anchor_model)
                controller.unload(model)

    return frames, identities


def _single_provider(provider: str, model: str | None, seed: int):
    if provider == "jev":
        return JevProvider()
    if provider == "llm":
        return OpenAIProvider(model=model)
    if provider == "korgis":
        if not model:
            raise typer.BadParameter("--model is required for provider=korgis")
        return KorgisProvider(model=model, seed=seed)
    raise typer.BadParameter("provider must be jev, llm, korgis, or llm-monolithic")


def _single_experiment_name(value: str) -> str:
    key = value.strip().lower().replace("_", "-")
    aliases = {
        "01": "routing",
        "01-routing": "routing",
        "routing": "routing",
        "02": "calibration",
        "02-calibration": "calibration",
        "calibration": "calibration",
        "03": "scaling",
        "03-parallel-scaling": "scaling",
        "scaling": "scaling",
        "04": "workflow",
        "04-workflow": "workflow",
        "workflow": "workflow",
        "05": "agent",
        "05-hybrid-agent": "agent",
        "agent": "agent",
    }
    resolved = aliases.get(key)
    if resolved is None:
        raise typer.BadParameter(
            "experiment must be routing, calibration, scaling, workflow, or agent"
        )
    return resolved


@app.command("prepare-data")
def prepare_data(
    cache_dir: Annotated[Path, typer.Option(help="Local dataset cache directory.")] = DEFAULT_CACHE,
) -> None:
    """Download canonical public datasets into the local gitignored cache."""
    paths = prepare_public_data(cache_dir)
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command("experiment")
def experiment(
    experiment_name: Annotated[
        str,
        typer.Argument(help="routing, calibration, scaling, workflow, or agent"),
    ],
    provider: Annotated[
        str,
        typer.Option(help="jev, llm, korgis, or llm-monolithic"),
    ] = "korgis",
    model: Annotated[
        str | None,
        typer.Option(help="Exact GPT model id or Korgis registry key."),
    ] = None,
    dataset: Annotated[
        str,
        typer.Option(help="smoke or public. Public is supported for routing/calibration."),
    ] = "smoke",
    profile: Annotated[
        str,
        typer.Option(help="budget, quick, standard, or full when --dataset public."),
    ] = "budget",
    scaling_repeats: Annotated[int, typer.Option(min=1)] = 5,
    seed: Annotated[int, typer.Option()] = 42,
    output: Annotated[
        Path, typer.Option()
    ] = Path("results/raw/experiment_results.csv"),
    html: Annotated[
        Path, typer.Option()
    ] = Path("results/experiment_report.html"),
    cache_dir: Annotated[Path, typer.Option()] = DEFAULT_CACHE,
    manage_korgis_model: Annotated[
        bool,
        typer.Option(help="Activate the requested Korgis model before the experiment."),
    ] = True,
) -> None:
    """Run one experiment and immediately build a drill-down HTML report."""
    resolved = _single_experiment_name(experiment_name)
    dataset = dataset.strip().lower()
    if dataset not in {"smoke", "public"}:
        raise typer.BadParameter("dataset must be smoke or public")
    if profile not in PUBLIC_PROFILES:
        raise typer.BadParameter("profile must be budget, quick, standard, or full")
    if dataset == "public" and resolved not in {"routing", "calibration"}:
        raise typer.BadParameter(
            "--dataset public is currently supported only for routing and calibration"
        )
    if provider == "llm-monolithic" and resolved not in {"workflow", "agent"}:
        raise typer.BadParameter(
            "llm-monolithic is supported only for workflow and agent experiments"
        )

    group = str(uuid.uuid4())
    korgis_identity: dict = {}
    requested_openai: list[str] = []
    requested_korgis: list[str] = []

    if provider == "llm-monolithic":
        mono_model = model or os.getenv("OPENAI_MODEL")
        if not mono_model:
            raise typer.BadParameter("--model or OPENAI_MODEL is required")
        requested_openai = [mono_model]
        frame = run_monolithic_workflows(OpenAIMonolithicProvider(model=mono_model))
        target = "04-workflow" if resolved == "workflow" else "05-hybrid-agent"
        frame = frame[frame["experiment"].eq(target)].copy()
    else:
        if provider == "llm":
            resolved_model = model or os.getenv("OPENAI_MODEL")
            if not resolved_model:
                raise typer.BadParameter("--model or OPENAI_MODEL is required")
            requested_openai = [resolved_model]
            decision_provider = _single_provider(provider, resolved_model, seed)
        elif provider == "korgis":
            if not model:
                raise typer.BadParameter("--model is required for provider=korgis")
            requested_korgis = [model]
            controller = KorgisController()
            controller.health()
            if manage_korgis_model:
                controller.activate(model)
            else:
                ensure_korgis_models_resident(controller, [model])
            decision_provider = _single_provider(provider, model, seed)
            korgis_identity[model] = controller.model_identity(model)
        else:
            decision_provider = _single_provider(provider, model, seed)

        if dataset == "public":
            prepare_public_data(cache_dir)
            sizes = PUBLIC_PROFILES[profile]
            public = run_public_classification(
                decision_provider,
                cache_dir=cache_dir,
                routing_max_cases=sizes["routing"],
                calibration_in_scope=sizes["in_scope"],
                calibration_oos=sizes["oos"],
                seed=seed,
            )
            target = (
                "01-routing-public"
                if resolved == "routing"
                else "02-calibration-public"
            )
            frame = public[public["experiment"].eq(target)].copy()
        else:
            frame = run_experiment(
                resolved,
                decision_provider,
                scaling_repeats=scaling_repeats,
            )

    suite = f"{dataset}-{resolved}"
    frame = _tag_run(frame, group, suite)
    append_results(frame, output)
    manifest = _record_manifest(
        frame,
        group=group,
        suite=suite,
        parameters={
            "experiment": resolved,
            "dataset": dataset,
            "profile": profile if dataset == "public" else None,
            "seed": seed,
            "scaling_repeats": scaling_repeats if resolved == "scaling" else None,
        },
        requested_openai_models=requested_openai,
        requested_korgis_models=requested_korgis,
        korgis_identity=korgis_identity,
    )
    build_report(output, html, run_group=group)
    typer.echo(f"Experiment: {resolved}")
    typer.echo(f"Provider: {provider}")
    typer.echo(f"Run group: {group}")
    typer.echo(f"Manifest: {manifest}")
    typer.echo(f"Dashboard: {html}")


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
    manifest = _record_manifest(
        frame,
        group=group,
        suite="smoke",
        parameters={"provider": provider, "scaling_repeats": scaling_repeats},
    )
    typer.echo(f"Wrote {len(frame)} rows to {output} (run_group={group})")
    typer.echo(f"Manifest: {manifest}")


@app.command()
def compare(
    output: Annotated[Path, typer.Option()] = DEFAULT_RAW,
    html: Annotated[Path, typer.Option()] = DEFAULT_REPORT,
    scaling_repeats: Annotated[int, typer.Option(min=1)] = 10,
    models: Annotated[
        str | None,
        typer.Option(help="Comma-separated OpenAI model matrix. Defaults to OPENAI_MODELS."),
    ] = None,
) -> None:
    """Run Jev and the GPT matrix on the smoke suite under one comparison group."""
    model_matrix = _model_matrix(models)
    group = str(uuid.uuid4())
    frames = []

    typer.echo("Running Jev workflow...")
    frames.append(_tag_run(run_all(JevProvider(), scaling_repeats=scaling_repeats), group, "smoke"))

    for model in model_matrix:
        typer.echo(f"Running decomposed LLM workflow: {model}...")
        frames.append(
            _tag_run(
                run_all(OpenAIProvider(model=model), scaling_repeats=scaling_repeats),
                group,
                "smoke",
            )
        )

    for model in model_matrix:
        typer.echo(f"Running monolithic workflow baseline: {model}...")
        frames.append(
            _tag_run(
                run_monolithic_workflows(OpenAIMonolithicProvider(model=model)),
                group,
                "smoke",
            )
        )

    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    manifest = _record_manifest(
        combined,
        group=group,
        suite="smoke",
        parameters={"scaling_repeats": scaling_repeats},
        requested_openai_models=model_matrix,
    )
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"Models: {', '.join(model_matrix)}")
    typer.echo(f"Manifest: {manifest}")
    typer.echo(f"Dashboard: {html}")


@app.command("compare-public")
def compare_public(
    profile: Annotated[
        str, typer.Option(help="budget, quick, standard, or full")
    ] = "standard",
    output: Annotated[Path, typer.Option()] = PUBLIC_RAW,
    html: Annotated[Path, typer.Option()] = PUBLIC_REPORT,
    cache_dir: Annotated[Path, typer.Option()] = DEFAULT_CACHE,
    seed: Annotated[int, typer.Option()] = 42,
    models: Annotated[
        str | None,
        typer.Option(help="Comma-separated OpenAI model matrix. Defaults to OPENAI_MODELS."),
    ] = None,
    include_local: Annotated[
        bool,
        typer.Option(help="Also benchmark local Korgis models."),
    ] = False,
    local_models: Annotated[
        str | None,
        typer.Option(help="Comma-separated Korgis model keys. Defaults to KORGIS_MODELS."),
    ] = None,
    manage_korgis_models: Annotated[
        bool,
        typer.Option(
            help="Use the Korgis admin API to activate local models sequentially and unload non-anchor models."
        ),
    ] = True,
    korgis_anchor_model: Annotated[
        str,
        typer.Option(help="Resident model used as the low-memory parking/default runtime."),
    ] = "nemotron-nano-4b",
    allow_moving_jev_model: Annotated[
        bool,
        typer.Option(help="Allow jev-latest/jev-preview instead of a pinned Jev version."),
    ] = False,
) -> None:
    """Run Jev, GPTs and optionally local Korgis models on the public benchmark."""
    if profile not in PUBLIC_PROFILES:
        raise typer.BadParameter("profile must be budget, quick, standard, or full")

    jev_model = os.getenv("JEV_MODEL", "jev-latest")
    if not allow_moving_jev_model and jev_model in {"jev-latest", "jev-preview"}:
        raise typer.BadParameter(
            "Public benchmarks require a pinned JEV_MODEL (for example jev-1.13.0). "
            "Use --allow-moving-jev-model only for exploratory runs."
        )

    model_matrix = _model_matrix(models)
    local_matrix = _local_model_matrix(local_models) if include_local else []
    sizes = PUBLIC_PROFILES[profile]
    prepare_public_data(cache_dir)
    group = str(uuid.uuid4())
    frames = []
    korgis_identity: dict = {}

    typer.echo(f"Running public {profile} benchmark: Jev...")
    jev_frame = run_public_classification(
        _decision_provider("jev"),
        cache_dir=cache_dir,
        routing_max_cases=sizes["routing"],
        calibration_in_scope=sizes["in_scope"],
        calibration_oos=sizes["oos"],
        seed=seed,
    )
    frames.append(_tag_run(jev_frame, group, f"public-{profile}"))

    for model in model_matrix:
        typer.echo(f"Running public {profile} benchmark: {model}...")
        frame = run_public_classification(
            _decision_provider("llm", model=model),
            cache_dir=cache_dir,
            routing_max_cases=sizes["routing"],
            calibration_in_scope=sizes["in_scope"],
            calibration_oos=sizes["oos"],
            seed=seed,
        )
        frames.append(_tag_run(frame, group, f"public-{profile}"))

    if local_matrix:
        local_frames, korgis_identity = _run_korgis_public(
            models=local_matrix,
            profile=profile,
            cache_dir=cache_dir,
            seed=seed,
            group=group,
            manage_runtime=manage_korgis_models,
            anchor_model=korgis_anchor_model,
        )
        frames.extend(local_frames)

    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    manifest = _record_manifest(
        combined,
        group=group,
        suite=f"public-{profile}",
        parameters={
            "profile": profile,
            "seed": seed,
            "routing_cases": sizes["routing"],
            "calibration_in_scope": sizes["in_scope"],
            "calibration_oos": sizes["oos"],
            "manage_korgis_models": manage_korgis_models if local_matrix else False,
            "korgis_anchor_model": korgis_anchor_model if local_matrix else None,
        },
        requested_openai_models=model_matrix,
        requested_korgis_models=local_matrix,
        korgis_identity=korgis_identity,
    )
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"GPT models: {', '.join(model_matrix)}")
    if local_matrix:
        typer.echo(f"Korgis models: {', '.join(local_matrix)}")
    typer.echo(f"Manifest: {manifest}")
    typer.echo(f"Dashboard: {html}")


@app.command("compare-local")
def compare_local(
    profile: Annotated[
        str, typer.Option(help="budget, quick, standard, or full")
    ] = "budget",
    output: Annotated[Path, typer.Option()] = Path("results/raw/local_results.csv"),
    html: Annotated[Path, typer.Option()] = Path("results/local_report.html"),
    cache_dir: Annotated[Path, typer.Option()] = DEFAULT_CACHE,
    seed: Annotated[int, typer.Option()] = 42,
    models: Annotated[
        str | None,
        typer.Option(help="Comma-separated Korgis model keys. Defaults to KORGIS_MODELS."),
    ] = None,
    manage_runtime: Annotated[
        bool,
        typer.Option(help="Activate models sequentially through the Korgis admin API."),
    ] = True,
    anchor_model: Annotated[
        str,
        typer.Option(help="Parking/default Korgis runtime used between larger local models."),
    ] = "nemotron-nano-4b",
) -> None:
    """Run only the local Korgis matrix; no paid cloud inference is used."""
    if profile not in PUBLIC_PROFILES:
        raise typer.BadParameter("profile must be budget, quick, standard, or full")

    prepare_public_data(cache_dir)
    local_matrix = _local_model_matrix(models)
    group = str(uuid.uuid4())
    frames, identities = _run_korgis_public(
        models=local_matrix,
        profile=profile,
        cache_dir=cache_dir,
        seed=seed,
        group=group,
        manage_runtime=manage_runtime,
        anchor_model=anchor_model,
    )
    combined = pd.concat(frames, ignore_index=True)
    append_results(combined, output)
    sizes = PUBLIC_PROFILES[profile]
    manifest = _record_manifest(
        combined,
        group=group,
        suite=f"local-{profile}",
        parameters={
            "profile": profile,
            "seed": seed,
            "routing_cases": sizes["routing"],
            "calibration_in_scope": sizes["in_scope"],
            "calibration_oos": sizes["oos"],
            "manage_korgis_models": manage_runtime,
            "korgis_anchor_model": anchor_model,
            "api_cost_scope": "local provider fee only; hardware and energy excluded",
        },
        requested_openai_models=[],
        requested_korgis_models=local_matrix,
        korgis_identity=identities,
    )
    build_report(output, html, run_group=group)
    typer.echo(f"Comparison group: {group}")
    typer.echo(f"Korgis models: {', '.join(local_matrix)}")
    typer.echo(f"Manifest: {manifest}")
    typer.echo(f"Dashboard: {html}")


@app.command()
def report(
    input_csv: Annotated[Path, typer.Option()] = DEFAULT_RAW,
    output_html: Annotated[Path, typer.Option()] = DEFAULT_REPORT,
    run_group: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Build the interactive HTML experiment explorer from raw benchmark rows."""
    build_report(input_csv, output_html, run_group=run_group)
    typer.echo(f"Wrote {output_html}")


if __name__ == "__main__":
    app()
