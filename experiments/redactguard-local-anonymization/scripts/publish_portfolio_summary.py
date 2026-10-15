"""Publish a safe, factual RedactGuard portfolio evidence summary.

The public artifact contains only dataset-level counts unless a COMPLETE,
manually approved metrics/manifest pair is provided. Raw cases, gold PII,
prompts, predictions and document evidence are never exported.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DATASETS = (
    ("smoke", "Smoke", "data/smoke/cases.jsonl", "Contract and pipeline checks", "smoke"),
    ("healthcare", "Healthcare", "data/healthcare/cases.jsonl", "Clinical and sensitive PII", "challenge"),
    ("ambiguous", "Ambiguous PII", "data/ambiguous/cases.jsonl", "Context-dependent private vs public data", "challenge"),
    ("challenge", "Hard cases", "data/challenge/cases.jsonl", "Semantic ambiguity and difficult PII", "challenge"),
    ("document-e2e", "Document E2E", "data/documents/manifest.jsonl", "Extraction plus privacy evaluation", "documents"),
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
        "source_path": "experiments/redactguard-local-anonymization/data/realistic/annotations/summary.json",
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


def publish_run(catalog: dict, run: Path, *, approved: bool) -> dict:
    """Append allowlisted aggregates from a reviewed complete run, never raw cases."""
    if not approved:
        raise ValueError("Explicit publication approval required for model performance")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    if (
        manifest.get("evaluation_schema") != "redactguard-evaluation-v3"
        or not isinstance(manifest.get("models"), list)
        or not isinstance(manifest.get("cases"), int)
        or manifest["cases"] < 1
    ):
        raise ValueError("Unsupported or incomplete benchmark manifest")
    datasets = catalog["datasets"]
    dataset = str(manifest.get("dataset", "")).replace("\\", "/")
    relevant = [d for d in datasets if d["source_path"].endswith(dataset) or
                dataset.endswith(d["source_path"].split("redactguard-local-anonymization/")[-1])]
    if len(relevant) != 1:
        raise ValueError("Unknown or non-versioned dataset: refusing publication")

    expected = relevant[0].get("cases", relevant[0].get("documents"))
    if manifest["cases"] != expected:
        raise ValueError("Partial runs cannot be published as complete comparisons")

    allowed_fields = (
        "pii_recall", "precision", "system_pii_recall",
        "system_leakage_rate", "inference_success_rate", "latency_p95_ms",
    )
    results = []
    for model in manifest["models"]:
        data = metrics.get(model)
        if not isinstance(model, str) or not isinstance(data, dict):
            raise ValueError("Missing model summary")
        if data.get("evaluation_schema") != "redactguard-evaluation-v3" or data.get("status") == "contract_failed":
            raise ValueError("Cannot publish contract-failed or unversioned results")
        if data.get("quality_available") is not True:
            raise ValueError("No valid scored inference for model")
        record = {"model": model, "dataset": relevant[0]["id"], "cases": expected}
        for field in allowed_fields:
            value = data.get(field)
            if field == "latency_p95_ms":
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or
                                          not math.isfinite(value) or value <= 0):
                    raise ValueError(f"Invalid {field}")
                record[field] = value
            else:
                record[field] = _fraction(value)
        if record["pii_recall"] is None or record["system_leakage_rate"] is None:
            raise ValueError("Required quality and risk metrics unavailable")
        results.append(record)
    catalog["models"] = results
    catalog["publication"]["status"] = "model_aggregates_published"
    catalog["publication"]["has_published_model_metrics"] = True
    relevant[0]["results_status"] = "published"
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--approve-public-aggregates", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/published/portfolio-summary.json"))
    args = parser.parse_args()
    summary = build_catalog(args.root, source_ref=args.source_ref)
    if args.run:
        summary = publish_run(summary, args.run, approved=args.approve_public_aggregates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
