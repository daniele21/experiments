from __future__ import annotations

import json
import os
import shutil
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import yaml

from redact_bench.history import append_history, build_history_entry
from redact_bench.history_dashboard import write_history_dashboard
from redact_bench.korgis_process import (
    ManagedKorgis,
    korgis_git_sha,
    prepare_korgis_models,
    resolve_korgis_repo,
)
from redact_bench.realistic_dataset import validate_realistic_dataset
from redact_bench.runner import run_compare, run_latency
from redact_bench.suite_artifacts import combine_model_runs


@dataclass(frozen=True)
class SuiteConfig:
    models: tuple[str, ...]
    dataset: Path
    profiles: Path
    results_dir: Path
    korgis_base_url: str
    runtime_strategy: str
    quality_warmups: int
    latency_case_ids: tuple[str, ...]
    latency_warmups: int
    latency_repeats: int
    download_missing_models: bool
    korgis_startup_timeout_seconds: float


def _resolve_path(value: str, root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (root / path).resolve()


def load_suite_config(path: str | Path, *, root: Path) -> SuiteConfig:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    suite = payload.get("suite") or {}

    models = tuple(str(value) for value in suite["models"])
    if not models:
        raise ValueError("suite.models must contain at least one model")

    runtime_strategy = str(suite.get("runtime_strategy", "restart_per_model"))
    if runtime_strategy != "restart_per_model":
        raise ValueError(
            "Unsupported suite.runtime_strategy. "
            "Current reproducible strategy is: restart_per_model"
        )

    latency = suite.get("latency") or {}
    return SuiteConfig(
        models=models,
        dataset=_resolve_path(str(suite["dataset"]), root),
        profiles=_resolve_path(str(suite["profiles"]), root),
        results_dir=_resolve_path(str(suite.get("results_dir", "results")), root),
        korgis_base_url=str(
            suite.get("korgis_base_url", "http://127.0.0.1:12435/v1")
        ).rstrip("/"),
        runtime_strategy=runtime_strategy,
        quality_warmups=int(suite.get("quality_warmups", 1)),
        latency_case_ids=tuple(str(value) for value in latency["case_ids"]),
        latency_warmups=int(latency.get("warmups", 5)),
        latency_repeats=int(latency.get("repeats", 30)),
        download_missing_models=bool(
            suite.get(
                "download_missing_models",
                suite.get("ensure_models", False),
            )
        ),
        korgis_startup_timeout_seconds=float(
            suite.get("korgis_startup_timeout_seconds", 600)
        ),
    )


@contextmanager
def _suite_environment(*, base_url: str, korgis_sha: str | None) -> Iterator[None]:
    keys = {
        "KORGIS_BASE_URL": base_url,
        "KORGIS_SOURCE_SHA": korgis_sha or "",
    }
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key, value in keys.items():
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _write_status(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def run_managed_suite(
    *,
    config_path: str | Path,
    experiment_root: Path,
    korgis_repo: str | Path | None = None,
    model_override: list[str] | None = None,
    download_missing_override: bool | None = None,
) -> Path:
    config = load_suite_config(config_path, root=experiment_root)
    models = tuple(model_override) if model_override else config.models
    if not models:
        raise ValueError("At least one model is required")
    download_missing = (
        config.download_missing_models
        if download_missing_override is None
        else download_missing_override
    )

    validation = validate_realistic_dataset(config.dataset)
    resolved_korgis = resolve_korgis_repo(
        korgis_repo,
        experiment_root=experiment_root,
    )
    source_sha = korgis_git_sha(resolved_korgis)

    suite_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-suite-"
        + uuid.uuid4().hex[:8]
    )
    suite_dir = config.results_dir / "suites" / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)
    status_path = suite_dir / "suite.json"
    started_at = datetime.now(timezone.utc).isoformat()
    base_status = {
        "suite_id": suite_id,
        "started_at": started_at,
        "models": list(models),
        "dataset_id": validation.get("dataset_id"),
        "runtime_strategy": config.runtime_strategy,
        "korgis_repo": str(resolved_korgis),
        "korgis_source_sha": source_sha,
        "korgis_base_url": config.korgis_base_url,
    }
    _write_status(status_path, {**base_status, "status": "preparing"})

    try:
        model_inventory = prepare_korgis_models(
            resolved_korgis,
            list(models),
            download_missing=download_missing,
        )
        base_status["model_inventory"] = model_inventory
        _write_status(status_path, {**base_status, "status": "preparing"})

        quality_runs: list[Path] = []
        latency_runs: list[Path] = []
        with _suite_environment(
            base_url=config.korgis_base_url,
            korgis_sha=source_sha,
        ):
            for index, model in enumerate(models, start=1):
                _write_status(
                    status_path,
                    {
                        **base_status,
                        "status": "running",
                        "current_model": model,
                        "model_index": index,
                        "model_count": len(models),
                    },
                )

                model_key = model.replace("/", "_")
                work_dir = suite_dir / "_work" / model_key
                with ManagedKorgis(
                    repo=resolved_korgis,
                    anchor_model=model,
                    log_path=suite_dir / "logs" / f"{model_key}.log",
                    startup_timeout_seconds=config.korgis_startup_timeout_seconds,
                    api_base=config.korgis_base_url,
                    reuse_existing=False,
                ):
                    quality_runs.append(
                        run_compare(
                            models=[model],
                            dataset_path=str(config.dataset),
                            profiles_path=str(config.profiles),
                            results_dir=str(work_dir / "quality"),
                            warmups=config.quality_warmups,
                        )
                    )
                    latency_runs.append(
                        run_latency(
                            models=[model],
                            dataset_path=str(config.dataset),
                            profiles_path=str(config.profiles),
                            results_dir=str(work_dir / "latency"),
                            warmups=config.latency_warmups,
                            repeats=config.latency_repeats,
                            case_ids=list(config.latency_case_ids),
                        )
                    )

        quality_dir = combine_model_runs(
            quality_runs,
            output=suite_dir / "quality",
            suite_id=suite_id,
            kind="quality",
        )
        latency_dir = combine_model_runs(
            latency_runs,
            output=suite_dir / "latency",
            suite_id=suite_id,
            kind="latency",
        )
        shutil.rmtree(suite_dir / "_work", ignore_errors=True)

        entry = build_history_entry(
            suite_id=suite_id,
            dataset_id=validation.get("dataset_id"),
            suite_dir=suite_dir,
            quality_dir=quality_dir,
            latency_dir=latency_dir,
            korgis_repo=resolved_korgis,
            korgis_sha=source_sha,
            korgis_base_url=config.korgis_base_url,
        )
        history_path = config.results_dir / "history.jsonl"
        append_history(history_path, entry)
        dashboard_path = write_history_dashboard(
            history_path,
            config.results_dir / "dashboard.html",
        )

        _write_status(
            status_path,
            {
                **base_status,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "quality": str(quality_dir),
                "latency": str(latency_dir),
                "history": str(history_path),
                "dashboard": str(dashboard_path),
            },
        )
        return suite_dir
    except Exception as exc:
        _write_status(
            status_path,
            {
                **base_status,
                "status": "failed",
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise
