"""Targeted managed Korgis quality probes for problematic document/model pairs.

A probe uses exactly the same RedactGuard scoring/preflight as the normal
quality suite, but executes only selected case IDs, without the latency phase.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redact_bench.datasets import load_dataset
from redact_bench.korgis_process import ManagedKorgis, korgis_git_sha, resolve_korgis_repo
from redact_bench.progress import TerminalProgress
from redact_bench.runner import run_compare
from redact_bench.suite import _suite_environment, load_suite_config


def run_quality_probe(
    *,
    config_path: Path,
    root: Path,
    models: list[str],
    case_ids: list[str],
    korgis_repo: Path | None = None,
    chunk_max_chars: int | None = None,
) -> Path:
    cfg = load_suite_config(config_path, root=root)
    if not models or not case_ids:
        raise ValueError("Provide at least one model and one case ID")
    models = list(dict.fromkeys(models))
    case_ids = list(dict.fromkeys(case_ids))
    available_cases = {case.case_id for case in load_dataset(cfg.dataset)}
    missing = sorted(set(case_ids) - available_cases)
    if missing:
        raise ValueError(f"Unknown case IDs: {', '.join(missing)}. Available: {', '.join(sorted(available_cases))}")

    korgis = resolve_korgis_repo(korgis_repo, experiment_root=root)
    probe_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-probe-" + uuid.uuid4().hex[:8]
    output = cfg.results_dir / "probes" / probe_id
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "probe.json"
    meta = {
        "probe_id": probe_id,
        "models": models,
        "cases": case_ids,
        "korgis_source_sha": korgis_git_sha(korgis),
        "chunk_max_chars": chunk_max_chars or cfg.chunk_max_chars,
        "inference_cache_max_entries": 0,
        "quality_warmups": 0,
        "results": {},
    }
    report_path.write_text(json.dumps({**meta, "status": "running"}, indent=2), encoding="utf-8")
    selected_chunk = chunk_max_chars if chunk_max_chars is not None else cfg.chunk_max_chars

    # Korgis process is isolated/restarted for each model, and its response
    # cache must be confirmed disabled before any diagnostic document is tested.
    try:
        with _suite_environment(
            base_url=cfg.korgis_base_url,
            korgis_sha=meta["korgis_source_sha"],
            timeout=cfg.benchmark_timeout_seconds,
            chunk_max_chars=selected_chunk,
            chunk_overlap_chars=cfg.chunk_overlap_chars,
            max_output_tokens=cfg.max_output_tokens,
            adaptive_subdivision=cfg.adaptive_subdivision,
        ):
            # User's existing native-ARM64 Korgis venv must already be installed.
            for model in models:
                print(f"[Probe] {model} | cases={','.join(case_ids)} | chunk={selected_chunk}", flush=True)
                with ManagedKorgis(
                    repo=korgis,
                    anchor_model=model,
                    log_path=output / "logs" / f"{model}.log",
                    startup_timeout_seconds=cfg.korgis_startup_timeout_seconds,
                    api_base=cfg.korgis_base_url,
                    inference_cache_max_entries=0,
                ):
                    path = run_compare(
                        models=[model],
                        dataset_path=str(cfg.dataset),
                        profiles_path=str(cfg.profiles),
                        results_dir=str(output / model),
                        warmups=0,
                        progress=TerminalProgress(interactive=False),
                        case_ids=case_ids,
                    )
                    meta["results"][model] = str(path)
                    report_path.write_text(
                        json.dumps({**meta, "status": "running"}, indent=2),
                        encoding="utf-8",
                    )
        report_path.write_text(
            json.dumps({**meta, "status": "completed"}, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        report_path.write_text(
            json.dumps({**meta, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, indent=2),
            encoding="utf-8",
        )
        raise
    return output
