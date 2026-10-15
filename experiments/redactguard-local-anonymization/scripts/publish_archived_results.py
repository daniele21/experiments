"""Create a privacy-safe RedactGuard aggregate snapshot from a reviewed results.zip.

No extraction occurs. Only manifest.json and metrics.json of explicitly selected,
complete evaluation-v3 quality runs are read. Prompt text, PII, documents, raw
responses, logs, host usernames and case-level evidence are never exported.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path

SOURCE_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_RE = re.compile(r"^\d{8}T\d{6}Z-suite-[0-9a-f]{8}$")
MODELS = frozenset({
    "nemotron-nano-4b", "nemotron-nano-4b-q8",
    "qwen3.5-4b-q4km", "qwen3.5-9b-q4km",
})
DATASETS = {
    "realistic": ("data/realistic", 11),
    "healthcare": ("data/healthcare/cases.jsonl", 48),
    "ambiguous": ("data/ambiguous/cases.jsonl", 48),
    "challenge": ("data/challenge/cases.jsonl", 46),
}
RATES = (
    "pii_recall", "system_pii_recall", "system_leakage_rate",
    "precision", "inference_success_rate",
)


def _read_json(archive: zipfile.ZipFile, path: str) -> dict:
    info = archive.getinfo(path)
    if info.file_size > 2_000_000:
        raise ValueError("Aggregate file too large")
    data = json.loads(archive.read(path))
    if not isinstance(data, dict):
        raise ValueError("Invalid aggregate JSON")
    return data


def _ratio(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError("Invalid ratio: " + name)
    return float(value)


def _dataset(name: object, cases: object) -> str:
    if not isinstance(name, str):
        raise ValueError("Missing dataset identity")
    normalized = name.replace("\\", "/").rstrip("/")
    for key, (path, size) in DATASETS.items():
        if (normalized == path or normalized.endswith("/" + path)) and (
            type(cases) is int and cases == size
        ):
            return key
    raise ValueError("Unapproved or incomplete dataset")


def build_archive_summary(archive_path: Path, catalog: dict, run_ids: list[str]) -> dict:
    """Build a new public summary; fail closed on duplicates and incomplete runs."""
    if catalog.get("schema_version") != 1 or (
        catalog.get("benchmark") != "redactguard-local-anonymization"
    ):
        raise ValueError("Invalid public catalog")
    if catalog.get("models") or catalog.get("publication", {}).get(
        "has_published_model_metrics"
    ):
        raise ValueError("Input catalog must be dataset-only")
    if not run_ids or len(run_ids) != len(set(run_ids)):
        raise ValueError("Select unique reviewed run IDs")

    result = copy.deepcopy(catalog)
    aggregates = []
    selected = []
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        for run in run_ids:
            if not RUN_RE.fullmatch(run):
                raise ValueError("Unsafe run identity")
            prefix = f"results/suites/{run}/quality"
            manifest = _read_json(archive, prefix + "/manifest.json")
            metrics = _read_json(archive, prefix + "/metrics.json")
            if manifest.get("kind") != "quality" or (
                manifest.get("evaluation_schema") != "redactguard-evaluation-v3"
            ):
                raise ValueError("Expected a quality v3 run")
            dataset = _dataset(manifest.get("dataset"), manifest.get("cases"))
            models = manifest.get("models")
            if not isinstance(models, list) or not models or (
                len(models) != len(set(models))
            ):
                raise ValueError("Invalid model list")
            if any(model not in MODELS for model in models):
                raise ValueError("Model not reviewed for publication")
            revision = manifest.get("benchmark_commit")
            if not isinstance(revision, str) or not SOURCE_RE.fullmatch(revision):
                raise ValueError("Missing benchmark commit")
            recorded = manifest.get("run_id")
            if not isinstance(recorded, str) or not recorded.startswith(run):
                raise ValueError("Mismatched run manifest")
            contract = (manifest.get("redactguard_contract") or {}).get(
                "snapshot_sha256"
            )
            if not isinstance(contract, str) or not re.fullmatch(
                r"[0-9a-f]{64}", contract
            ):
                raise ValueError("Unversioned evaluation contract")
            cohort = hashlib.sha256(
                f"{run}|{revision}|{contract}|{dataset}".encode()
            ).hexdigest()[:16]
            selected.append({
                "dataset": dataset, "run_id": recorded,
                "benchmark_commit": revision, "cohort_id": cohort,
                "model_count": len(models),
            })
            for model in models:
                identifier = (dataset, model)
                if identifier in seen:
                    raise ValueError("Duplicate model/dataset in reviewed runs")
                seen.add(identifier)
                summary = metrics.get(model)
                if not isinstance(summary, dict) or (
                    summary.get("evaluation_schema") != "redactguard-evaluation-v3"
                    or summary.get("status") != "ok"
                    or summary.get("quality_available") is not True
                ):
                    raise ValueError("Unscored or contract-failed model")
                count = summary.get("cases")
                evaluated = summary.get("evaluated_cases")
                failed = summary.get("inference_failures")
                if any(type(x) is not int for x in (count, evaluated, failed)) or (
                    count != manifest["cases"] or evaluated < 1 or failed < 0
                    or evaluated + failed != count
                ):
                    raise ValueError("Incomplete model coverage")
                rates = {key: _ratio(summary.get(key), key) for key in RATES}
                if abs(rates["inference_success_rate"] - evaluated / count) > 1e-4:
                    raise ValueError("Inconsistent success rate")
                latency = summary.get("latency_p95_ms")
                if isinstance(latency, bool) or not isinstance(
                    latency, (int, float)
                ) or not math.isfinite(latency) or latency <= 0:
                    raise ValueError("Invalid observed latency")
                provenance = {
                    "run_id": recorded,
                    "created_at": manifest.get("created_at"),
                    "benchmark_commit": revision,
                    "contract_snapshot_sha256": contract,
                    "backend": "local-korgis",
                    "cohort_id": cohort,
                    "comparison_scope": "same_run_exploratory",
                }
                aggregates.append({
                    "model": model, "dataset": dataset, "cases": count,
                    "evaluated_cases": evaluated, "inference_failures": failed,
                    "run_id": recorded, **rates,
                    "latency_p95_ms": float(latency),
                    "latency_provenance": (
                        "observed_quality_run_p95_not_repeated_latency_benchmark"
                    ),
                    "provenance": provenance,
                })
    if not {row["dataset"] for row in aggregates}.issubset(
        {d["id"] for d in result["datasets"]}
    ):
        raise ValueError("Unversioned dataset")

    result["models"] = sorted(
        aggregates, key=lambda entry: (entry["dataset"], entry["model"])
    )
    for item in result["datasets"]:
        if any(x["dataset"] == item["id"] for x in aggregates):
            item["results_status"] = "published"
    result["publication"].update({
        "status": "model_aggregates_published",
        "has_published_model_metrics": True,
        "run_count": len(selected),
        "latency_provenance": "quality_run_observed_p95",
    })
    result["source"].update({
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "selection_policy": (
            "reviewed complete v3 quality runs; one selected run "
            "per dataset/model; no original text"
        ),
        "selected_runs": selected,
    })
    result["limitations"] = [
        item for item in result["limitations"]
        if "No comparable measured model runs" not in item
    ]
    result["limitations"].extend([
        "Observed p95 values come from quality runs, not repeated latency runs.",
        "Healthcare and Ambiguous aggregate different model cohorts and benchmark commits; they are not controlled head-to-head rankings.",
        "Realistic-document runs include inference failures; system-level recall and leakage reflect failures.",
        "Historical run provenance is retained; gold spans are not independently human-reviewed.",
    ])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    summary = build_archive_summary(args.archive, catalog, args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
