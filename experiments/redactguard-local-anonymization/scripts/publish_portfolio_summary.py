"""Publish a safe, factual RedactGuard portfolio evidence summary.

The public artifact contains only dataset-level counts unless a COMPLETE,
manually approved metrics/manifest pair is provided. Raw cases, gold PII,
prompts, predictions and document evidence are never exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

DATASETS = (
    ("smoke", "Smoke", "data/smoke/cases.jsonl", "Contract and pipeline checks", "smoke"),
    (
        "healthcare", "Healthcare", "data/healthcare/cases.jsonl",
        "Clinical and sensitive PII", "challenge",
    ),
    (
        "ambiguous", "Ambiguous PII", "data/ambiguous/cases.jsonl",
        "Context-dependent private vs public data", "challenge",
    ),
    (
        "challenge", "Hard cases", "data/challenge/cases.jsonl",
        "Semantic ambiguity and difficult PII", "challenge",
    ),
    (
        "document-e2e", "Document E2E", "data/documents/manifest.jsonl",
        "Extraction plus privacy evaluation", "documents",
    ),
)


def _read_jsonl_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        raise ValueError(f"Empty dataset: {path}")
    return len(rows)


def build_catalog(root: Path, *, source_ref: str) -> dict:
    if not source_ref:
        raise ValueError("An explicit repository source ref is required")
    datasets = []
    for key, title, path, focus, family in DATASETS:
        datasets.append({
            "id": key,
            "title": title,
            "kind": family,
            "focus": focus,
            "cases": _read_jsonl_count(root / path),
            "source_path": f"experiments/redactguard-local-anonymization/{path}",
            "results_status": "no_published_run",
        })

    realistic_path = root / "data/realistic/annotations/summary.json"
    summary = json.loads(realistic_path.read_text(encoding="utf-8"))
    documents = summary["documents"]
    spans = summary["total_spans"]
    if not isinstance(documents, int) or documents <= 0 or not isinstance(spans, int) or spans <= 0:
        raise ValueError("Invalid realistic dataset annotation summary")
    datasets.append({
        "id": "realistic",
        "title": "Realistic documents",
        "kind": "documents",
        "focus": "Heterogeneous formats and annotated PII",
        "documents": documents,
        "gold_spans": spans,
        "source_path": (
            "experiments/redactguard-local-anonymization/"
            "data/realistic/annotations/summary.json"
        ),
        "results_status": "no_published_run",
    })
    return {
        "schema_version": 1,
        "benchmark": "redactguard-local-anonymization",
        "source": {
            "repository": "daniele21/experiments",
            "ref": source_ref,
            "path": "experiments/redactguard-local-anonymization",
        },
        "publication": {
            "status": "dataset_evidence_only",
            "has_published_model_metrics": False,
            "contains_raw_pii": False,
        },
        "datasets": datasets,
        "models": [],
        "metric_contract": {
            "model_quality": ["pii_recall", "precision"],
            "privacy_risk": ["system_pii_recall", "system_leakage_rate"],
            "reliability": ["inference_success_rate"],
            "latency": ["latency_p95_ms"],
        },
        "limitations": [
            "Dataset counts and gold spans are NOT model performance results.",
            "No comparable measured model runs have been published for this benchmark.",
            "Smoke datasets are not sufficient to claim general model quality.",
            "Realistic annotations are machine-validated, not independently human-reviewed.",
        ],
    }


def _fraction(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and 0 <= value <= 1 else None


def _dataset_id(catalog: dict, path: str) -> dict:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or normalized.endswith("/"):
        raise ValueError("Invalid or unspecified dataset")
    matches = [
        entry for entry in catalog["datasets"]
        if normalized == entry["source_path"]
        or normalized == entry["source_path"].split("redactguard-local-anonymization/")[-1]
        or (
            entry["id"] == "realistic"
            and normalized in {"data/realistic", "data/realistic/"}
        )
    ]
    if len(matches) != 1:
        raise ValueError(f"Unknown or non-versioned dataset: {normalized}")
    return matches[0]


def _safe_latency(value: object) -> float | None:
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError("Invalid latency_p95_ms")
    return float(value)


def _model_aggregate(
    model: str, data: dict, manifest: dict, dataset: dict, run_id: str
) -> dict:
    if (
        data.get("evaluation_schema") != "redactguard-evaluation-v3"
        or data.get("status") == "contract_failed"
    ):
        raise ValueError("Cannot publish contract-failed or unversioned results")
    if data.get("quality_available") is not True:
        raise ValueError("No valid scored inference for model")
    cases = manifest["cases"]
    if data.get("cases") != cases:
        raise ValueError("Model case coverage does not match complete run")
    evaluated = data.get("evaluated_cases")
    failures = data.get("inference_failures")
    if (
        not isinstance(evaluated, int)
        or not isinstance(failures, int)
        or evaluated <= 0
        or failures < 0
        or evaluated + failures != cases
    ):
        raise ValueError("Run model completeness cannot be verified")

    allowed_fractions = (
        "pii_recall", "precision", "system_pii_recall",
        "system_leakage_rate", "inference_success_rate",
    )
    values = {key: _fraction(data.get(key)) for key in allowed_fractions}
    if values["pii_recall"] is None or values["system_leakage_rate"] is None:
        raise ValueError("Required quality and risk metrics unavailable")
    if any(values[k] is None for k in ("precision", "inference_success_rate")):
        raise ValueError("Missing required valid contract or quality metrics")
    if abs(values["inference_success_rate"] - evaluated / cases) > 0.0001:
        raise ValueError("Inconsistent reported inference success rate")

    return {
        "model": model,
        "dataset": dataset["id"],
        "cases": cases,
        "evaluated_cases": evaluated,
        "inference_failures": failures,
        "run_id": run_id,
        **values,
        "latency_p95_ms": _safe_latency(data.get("latency_p95_ms")),
    }


def publish_runs(catalog: dict, runs: list[Path], *, approved: bool) -> dict:
    """Project reviewed COMPLETE runs into public aggregates, without raw PII.

    One explicit source run per model/dataset pair. Different runs are NOT
    treated as a verified head-to-head or a global Pareto frontier.
    """
    if not approved:
        raise ValueError("Explicit publication approval required for model performance")
    if not runs:
        raise ValueError("No reviewed run directories selected")
    all_models: list[dict] = []
    used: set[tuple[str, str]] = set()
    for run in runs:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        if (
            manifest.get("evaluation_schema") != "redactguard-evaluation-v3"
            or not isinstance(manifest.get("models"), list)
            or not manifest["models"]
            or not isinstance(manifest.get("cases"), int)
            or isinstance(manifest.get("cases"), bool)
            or manifest["cases"] < 1
            or not isinstance(metrics, dict)
        ):
            raise ValueError("Unsupported or incomplete benchmark manifest")
        entry = _dataset_id(catalog, str(manifest.get("dataset") or ""))
        expected = entry.get("cases", entry.get("documents"))
        if manifest["cases"] != expected:
            raise ValueError("Partial runs cannot be published as complete comparisons")
        run_id = str(manifest.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("Missing recorded run identity")
        backend = str(manifest.get("backend") or "unknown")
        evaluation_schema = manifest["evaluation_schema"]
        contract = manifest.get("redactguard_contract") or {}
        # Preserve provenance, but never publish potentially sensitive
        # prompt contracts, model input, gold labels or runtime secret settings.
        contract_hash = contract.get("snapshot_sha256")
        if not isinstance(contract_hash, str) or len(contract_hash) < 12:
            contract_hash = None
        environment = manifest.get("host") or {}
        host = {
            key: environment[key] for key in ("system", "machine")
            if isinstance(environment.get(key), str)
        }
        cohort_id = hashlib.sha256(json.dumps({
            "run_id": run_id, "dataset": entry["id"],
            "source_ref": catalog["source"]["ref"],
            "contract": contract_hash, "backend": backend,
            "schema": evaluation_schema, "host": host,
        }, sort_keys=True).encode()).hexdigest()[:16]

        for model in manifest["models"]:
            if not isinstance(model, str) or not model.strip():
                raise ValueError("Invalid model identity")
            identifier = (entry["id"], model)
            if identifier in used:
                raise ValueError(
                    "Duplicate model/dataset across runs; select one reviewed version"
                )
            used.add(identifier)
            summary = metrics.get(model)
            if not isinstance(summary, dict):
                raise ValueError("Missing model summary")
            record = _model_aggregate(model, summary, manifest, entry, run_id)
            record["provenance"] = {
                "run_id": run_id,
                "created_at": manifest.get("created_at"),
                "benchmark_commit": manifest.get("benchmark_commit"),
                "backend": backend,
                "contract_snapshot_sha256": contract_hash,
                "host": host,
                "cohort_id": cohort_id,
                "comparison_scope": "same_run_exploratory",
            }
            all_models.append(record)
        entry["results_status"] = "published"
    catalog["models"] = sorted(all_models, key=lambda m: (m["dataset"], m["model"]))
    catalog["publication"]["status"] = "model_aggregates_published"
    catalog["publication"]["has_published_model_metrics"] = True
    catalog["publication"]["run_count"] = len(runs)
    return catalog


def publish_run(catalog: dict, run: Path, *, approved: bool) -> dict:
    """Backwards-compatible single-run publication API."""
    return publish_runs(catalog, [run], approved=approved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-ref", required=True)
    parser.add_argument(
        "--run", type=Path, action="append", default=[],
        help="Reviewed COMPLETE run directory (repeat for multiple suites)",
    )
    parser.add_argument("--approve-public-aggregates", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("results/published/portfolio-summary.json")
    )
    args = parser.parse_args()
    summary = build_catalog(args.root, source_ref=args.source_ref)
    if args.run:
        summary = publish_runs(summary, args.run, approved=args.approve_public_aggregates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
