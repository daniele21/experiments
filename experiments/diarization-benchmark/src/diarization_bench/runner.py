from __future__ import annotations

import json
import platform
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CaseSpec, ModelSpec
from .metrics import Segment, evaluate, load_rttm
from .runtime import FluidAudioRuntime


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def plan(models: list[ModelSpec], cases: list[CaseSpec]) -> dict[str, Any]:
    return {
        "models": [
            {
                "key": model.key,
                "engine": model.engine,
                "family": model.family,
                "mode": model.mode,
                "max_speakers": model.max_speakers,
                "options": model.options,
            }
            for model in models
        ],
        "cases": [
            {
                "id": case.case_id,
                "audio": str(case.audio),
                "reference_rttm": str(case.reference_rttm),
                "tags": case.tags,
            }
            for case in cases
        ],
        "attempts": len(models) * len(cases),
    }


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_model[record["model_key"]].append(record)

    models: dict[str, Any] = {}
    for model_key, items in by_model.items():
        models[model_key] = {
            "cases": len(items),
            "mean_der": statistics.fmean(item["metrics"]["der"] for item in items),
            "mean_jer": statistics.fmean(item["metrics"]["jer"] for item in items),
            "speaker_count_exact_rate": statistics.fmean(
                1.0 if item["metrics"]["speaker_count_exact"] else 0.0 for item in items
            ),
            "mean_inference_rtf": statistics.fmean(
                item["runtime"]["inference_rtf"] for item in items
            ),
            "mean_wall_rtf": statistics.fmean(item["runtime"]["wall_rtf"] for item in items),
            "max_peak_rss_mb": max(item["runtime"]["peak_rss_mb"] for item in items),
        }
    return {"models": models}


def run(
    experiment_root: Path,
    models: list[ModelSpec],
    cases: list[CaseSpec],
    *,
    run_id: str | None = None,
) -> Path:
    run_id = run_id or _run_id()
    run_dir = experiment_root / "results" / "runs" / run_id
    if run_dir.exists():
        raise FileExistsError(f"Run already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    runtime = FluidAudioRuntime(experiment_root)
    problems = runtime.preflight()
    if problems:
        raise RuntimeError("Preflight failed: " + "; ".join(problems))

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "models": [model.key for model in models],
        "cases": [case.case_id for case in cases],
        "metric_protocol": {
            "der_collar_seconds": 0,
            "overlap": "included",
            "primary": "DER",
            "secondary": ["JER", "speaker_count_exact", "inference_rtf", "peak_rss_mb"],
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)

    records: list[dict[str, Any]] = []
    for model in models:
        for case in cases:
            if not case.audio.exists():
                raise FileNotFoundError(case.audio)
            if not case.reference_rttm.exists():
                raise FileNotFoundError(case.reference_rttm)

            result = runtime.run(model, case.audio)
            payload = result.payload
            duration = float(payload["audio_duration_seconds"])
            inference_seconds = float(payload["inference_seconds"])
            hypothesis = [
                Segment(
                    speaker=str(item["speaker"]),
                    start=float(item["start"]),
                    end=float(item["end"]),
                )
                for item in payload["segments"]
                if float(item["end"]) > float(item["start"])
            ]
            reference = load_rttm(case.reference_rttm)
            metrics = evaluate(reference, hypothesis)

            record = {
                "run_id": run_id,
                "model_key": model.key,
                "model_family": model.family,
                "engine": model.engine,
                "case_id": case.case_id,
                "tags": case.tags,
                "metrics": metrics,
                "runtime": {
                    "audio_duration_seconds": duration,
                    "model_load_seconds": float(payload["model_load_seconds"]),
                    "audio_prepare_seconds": float(payload["audio_prepare_seconds"]),
                    "inference_seconds": inference_seconds,
                    "inference_rtf": inference_seconds / duration if duration else 0.0,
                    "wall_seconds": result.wall_seconds,
                    "wall_rtf": result.wall_seconds / duration if duration else 0.0,
                    "peak_rss_mb": result.peak_rss_mb,
                    "cpu_seconds": result.cpu_seconds,
                },
                "segments": payload["segments"],
                "runtime_metadata": payload.get("metadata") or {},
            }
            records.append(record)
            _append_jsonl(run_dir / "evaluation.jsonl", record)
            _append_jsonl(
                run_dir / "raw.jsonl",
                {
                    "run_id": run_id,
                    "model_key": model.key,
                    "case_id": case.case_id,
                    "payload": payload,
                    "stderr": result.stderr,
                },
            )

    aggregate = _aggregate(records)
    _write_json(run_dir / "aggregates.json", aggregate)
    _write_json(
        run_dir / "report.json",
        {
            "run_id": run_id,
            "protocol": manifest["metric_protocol"],
            **aggregate,
        },
    )
    return run_dir
