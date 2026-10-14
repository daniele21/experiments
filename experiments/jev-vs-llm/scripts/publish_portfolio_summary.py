"""Export an explicit, privacy-safe/publication-safe summary for the portfolio.

The source may contain proprietary benchmark results, raw prompts, or case data.
Never copy source subtrees into the published artifact. Build the projection from
a strict provider and field allowlist.

Jev / TypeSafe / CLM results are always withheld here. Publishing them would
require separate legal review and an intentionally reviewed code change.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EXPERIMENTS = ("routing", "calibration", "scaling", "workflow", "agent")
# Explicitly approved, non-Jev provider families. Add new providers only
# after checking data provenance and publication terms.
ALLOWED_PROVIDERS = frozenset({
    "local-korgis", "korgis", "llm-workflow", "llm-monolithic",
    "openai", "minicpm-api", "minicpm",
})
RESTRICTED_TOKENS = ("jev", "typesafe", "clm", "systemone", "system-one")


def _safe_metric(value: Any, *, minimum: float = 0.0, maximum: float = math.inf) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        return None
    return number


def _allowed(row: dict[str, Any]) -> bool:
    provider = str(row.get("provider") or "").strip().lower()
    model = str(row.get("model") or "").strip().lower()
    if not provider or not model:
        return False
    if any(token in provider or token in model for token in RESTRICTED_TOKENS):
        return False
    return provider in ALLOWED_PROVIDERS


def build_public_summary(payload: dict[str, Any], *, source_ref: str, source_path: str) -> dict[str, Any]:
    if not source_ref or not source_path or not isinstance(payload, dict):
        raise ValueError("A versioned source_ref, source_path, and payload are required")

    routing: list[dict[str, Any]] = []
    for row in payload.get("overview", []):
        if not isinstance(row, dict) or not _allowed(row):
            continue
        accuracy = _safe_metric(row.get("accuracy"), maximum=1.0)
        p50 = _safe_metric(row.get("latency_p50_ms"), minimum=0.0001)
        count = _safe_metric(row.get("requests"), minimum=1)
        if accuracy is None or p50 is None or count is None or not count.is_integer():
            continue
        metric: dict[str, Any] = {
            "model": str(row["model"]),
            "provider": str(row["provider"]),
            "requests": int(count),
            "accuracy": accuracy,
            "latency_p50_ms": p50,
        }
        p95 = _safe_metric(row.get("latency_p95_ms"), minimum=0.0001)
        valid = _safe_metric(row.get("valid_rate"), maximum=1.0)
        if p95 is not None:
            metric["latency_p95_ms"] = p95
        if valid is not None:
            metric["valid_rate"] = valid
        routing.append(metric)

    if not routing:
        raise ValueError("No publishable provider aggregates; refusing empty artifact")

    # Duplicate model aggregates across distinct evaluation modes would be
    # misleading: refuse rather than silently selecting a winner.
    identifiers = [(row["provider"], row["model"]) for row in routing]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate provider/model aggregates need separate run metadata")

    routing.sort(key=lambda row: (-row["accuracy"], row["latency_p50_ms"], row["model"]))
    counts: dict[int, int] = {}
    for row in routing:
        counts[row["requests"]] = counts.get(row["requests"], 0) + 1
    predominant = max(counts, key=lambda number: (counts[number], number))
    cohort = [row for row in routing if row["requests"] == predominant]
    other = [row for row in routing if row["requests"] != predominant]

    experiment_states: list[dict[str, Any]] = []
    statuses = payload.get("experiments") or {}
    for experiment_id in EXPERIMENTS:
        entry = statuses.get(experiment_id) or {}
        has_source_data = bool(entry.get("has_data"))
        is_routing = experiment_id == "routing"
        state = "published_subset" if is_routing else (
            "not_published" if not has_source_data else "withheld_pending_review"
        )
        experiment_states.append({
            "id": experiment_id,
            "status": state,
            "published_model_count": len(routing) if is_routing else 0,
        })

    providers = sorted({row["provider"] for row in routing})
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "jev-vs-llm",
        "publication": {
            "scope": "non_restricted_aggregates_only",
            "restricted_jev_typesafe_clm_metrics_included": False,
            "raw_case_data_included": False,
            "comparison_status": "partial_provider_subset",
        },
        "source": {
            "repository": "daniele21/experiments",
            "ref": source_ref,
            "path": source_path,
        },
        "experiments": experiment_states,
        "routing": {
            "status": "published_subset",
            "providers": providers,
            "models": routing,
            "total_model_requests": sum(row["requests"] for row in routing),
            "comparison_group": {
                "requests_per_model": predominant,
                "model_count": len(cohort),
                "models": [row["model"] for row in cohort],
                "comparability": "equal_request_counts_only",
                "note": "Same case count does not establish identical cases, prompts or configurations.",
            },
            "other_runs": [{"model": row["model"], "requests": row["requests"]} for row in other],
        },
        "limitations": [
            "No JEV/TypeSafe/CLM numeric metrics are released by this exporter.",
            "No direct JEV-vs-LLM comparison can be claimed from this artifact.",
            "Other experiment types require separately reviewed public aggregates.",
            "Matching case counts alone do not prove paired identical benchmark samples.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Exported benchmark_data.json")
    parser.add_argument("--source-ref", required=True, help="Immutable source commit SHA or Git ref")
    parser.add_argument("--source-path", required=True, help="Source repository-relative path")
    parser.add_argument("--output", type=Path, default=Path("results/published/portfolio-summary.json"))
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = build_public_summary(source, source_ref=args.source_ref, source_path=args.source_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Published {len(result['routing']['models'])} approved model aggregates to {args.output}")


if __name__ == "__main__":
    main()
