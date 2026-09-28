from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_history(path: str | Path) -> list[dict[str, Any]]:
    history_path = Path(path)
    if not history_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        history_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSONL in {history_path} at line {line_number}: {exc}"
            ) from exc
    return entries


def append_history(path: str | Path, entry: dict[str, Any]) -> None:
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _quality_view(summary: dict) -> dict:
    micro = summary.get("micro", summary)
    macro = summary.get("macro", {})
    return {
        "status": micro.get("status"),
        "quality_available": micro.get("quality_available"),
        "micro_recall": micro.get("pii_recall"),
        "macro_recall": macro.get("pii_recall"),
        "system_recall": micro.get("system_pii_recall"),
        "micro_leakage": micro.get("leakage_rate"),
        "macro_leakage": macro.get("leakage_rate"),
        "system_leakage": micro.get("system_leakage_rate"),
        "micro_precision": micro.get("precision"),
        "macro_precision": macro.get("precision"),
        "zero_leak_documents": micro.get("zero_leak_document_rate"),
        "inference_success_rate": micro.get("inference_success_rate"),
        "contract_valid_rate": micro.get("contract_valid_rate"),
        "truncation_rate": micro.get("truncation_rate"),
        "span_resolution_rate": micro.get("span_resolution_rate"),
        "evaluated_cases": micro.get("evaluated_cases"),
        "cases": micro.get("cases"),
        "quality_p50_ms": micro.get("latency_p50_ms"),
        "quality_p95_ms": micro.get("latency_p95_ms"),
        "by_type": summary.get("by_type", {}),
    }


def _latency_view(summary: dict) -> dict:
    micro = summary.get("micro", summary)
    return {
        "p50_ms": micro.get("latency_p50_ms"),
        "p95_ms": micro.get("latency_p95_ms"),
        "p99_ms": micro.get("latency_p99_ms"),
        "valid_output_rate": micro.get("valid_output_rate"),
    }


def build_history_entry(
    *,
    suite_id: str,
    dataset_id: str | None,
    suite_dir: Path,
    quality_dir: Path,
    latency_dir: Path,
    korgis_repo: Path,
    korgis_sha: str | None,
    korgis_base_url: str,
) -> dict[str, Any]:
    quality_manifest = _load_json(quality_dir / "manifest.json")
    quality_metrics = _load_json(quality_dir / "metrics.json")
    latency_manifest = _load_json(latency_dir / "manifest.json")
    latency_metrics = _load_json(latency_dir / "metrics.json")

    models: dict[str, dict] = {}
    for model in quality_manifest.get("models", []):
        models[model] = {
            "quality": _quality_view(quality_metrics[model]),
            "latency": _latency_view(latency_metrics[model]),
        }

    return {
        "schema_version": "redactguard-suite-history-v2",
        "suite_id": suite_id,
        "created_at": quality_manifest.get("created_at"),
        "dataset_id": dataset_id,
        "models": models,
        "benchmark_commit": quality_manifest.get("benchmark_commit"),
        "evaluation_schema": quality_manifest.get("evaluation_schema"),
        "redactguard_contract": quality_manifest.get("redactguard_contract"),
        "preflight": quality_manifest.get("preflight"),
        "host": quality_manifest.get("host"),
        "runtime_strategy": "restart_per_model",
        "korgis": {
            "repo": str(korgis_repo),
            "source_sha": korgis_sha,
            "base_url": korgis_base_url,
            "runtime_identity": quality_manifest.get("korgis", {}).get(
                "runtime_identity"
            ),
        },
        "paths": {
            "suite": str(suite_dir),
            "quality": str(quality_dir),
            "latency": str(latency_dir),
        },
        "latency_case_ids": latency_manifest.get("case_ids", []),
        "latency_repeats": latency_manifest.get("repeats_per_case"),
    }
