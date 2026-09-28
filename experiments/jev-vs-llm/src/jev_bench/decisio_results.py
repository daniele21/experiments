"""Import completed Decisio artifacts into the shared benchmark dashboard dataset."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from jev_bench.report import build_report


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decisio_output_frame(matrix_directory: Path, model: str, output: Path) -> pd.DataFrame:
    """Convert one completed Decisio model directory to the common row schema."""
    fixture = _load_json(output / "fixture.json")
    manifest = _load_json(output / "manifest.json")
    rows = [
        json.loads(line)
        for line in (output / "rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = {case["case_id"]: case for case in fixture["cases"]}
    run_group = str(uuid.uuid5(uuid.NAMESPACE_URL, str(matrix_directory.resolve())))
    timestamp = manifest.get("timestamp")
    dataset = manifest.get("dataset", "banking77")
    device = manifest.get("config", {}).get("device", "cpu")
    dataset_type = "public" if dataset == "banking77" else "smoke"
    experiment = "01-routing-public" if dataset_type == "public" else "01-routing"

    records = []
    for row in rows:
        case = cases[row["case_id"]]
        metadata = case.get("metadata", {})
        result = row.get("result") or {}
        runtime = row.get("runtime") or {}
        choice = row.get("choice")
        distribution = result.get("distribution") or {}
        method = row["method"]
        records.append(
            {
                "experiment": experiment,
                "case_id": row["case_id"],
                "input_state": case.get("state"),
                "provider": "local-decisio",
                "model": model,
                "question_id": fixture["question"]["id"],
                "expected": row.get("expected"),
                "actual": choice,
                "correct": bool(row.get("correct")),
                "confidence": distribution.get(choice),
                "predicted_probability": distribution.get(choice),
                "latency_ms": row.get("latency_ms"),
                "input_tokens": runtime.get("physically_evaluated_tokens"),
                "cached_input_tokens": runtime.get("reused_prefix_tokens"),
                "output_tokens": result.get("generated_tokens", 0),
                "estimated_cost_usd": 0.0,
                "valid": bool(row.get("valid")),
                "error": row.get("error"),
                "primary_metric": True,
                "run_id": str(uuid.uuid5(uuid.UUID(run_group), f"{model}:{method}")),
                "run_group": run_group,
                "suite": f"decisio-{dataset_type}-routing",
                "run_timestamp_utc": timestamp,
                "runner_location": "local",
                "dataset": dataset,
                "dataset_revision": metadata.get("dataset_revision"),
                "source_split": metadata.get("source_split"),
                "difficulty": metadata.get("difficulty", "in_scope"),
                "benchmark_tier": metadata.get("benchmark_tier", dataset_type),
                "experiment_source": metadata.get("experiment_source", experiment),
                "oos_filter": None,
                "thinking_mode": "standard",
                "dataset_type": dataset_type,
                "configuration_id": f"{method}-{device}",
                "scorer_method": method,
                "inference_device": device,
                "logical_input_tokens": runtime.get("logical_input_tokens"),
                "physically_evaluated_tokens": runtime.get("physically_evaluated_tokens"),
                "reused_prefix_tokens": runtime.get("reused_prefix_tokens"),
                "reuse_ratio": runtime.get("reuse_ratio"),
                "shared_prefix_calls": runtime.get("shared_prefix_calls"),
                "shared_prefix_fallbacks": runtime.get("shared_prefix_fallbacks"),
            }
        )
    return pd.DataFrame(records)


def publish_decisio_results(
    matrix_directory: Path,
    model_outputs: list[tuple[str, Path]],
    *,
    output_csv: Path,
    report_html: Path,
) -> int:
    """Upsert completed Decisio rows and rebuild the shared dashboard."""
    frames = [
        decisio_output_frame(matrix_directory, model, output)
        for model, output in model_outputs
    ]
    if not frames:
        return 0
    imported = pd.concat(frames, ignore_index=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if output_csv.exists():
        existing = pd.read_csv(output_csv)
        existing = existing[~existing["run_group"].astype(str).isin(imported["run_group"])]
        imported = pd.concat([existing, imported], ignore_index=True)
    temporary = output_csv.with_suffix(output_csv.suffix + ".tmp")
    imported.to_csv(temporary, index=False)
    temporary.replace(output_csv)
    build_report(output_csv, report_html, run_group="latest_per_model")
    return sum(len(frame) for frame in frames)
