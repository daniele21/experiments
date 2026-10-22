"""Immutable, latest-attempt consolidation of compatible benchmark evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import read_jsonl_records, sha256_file

from model_capability_bench.runner.aggregation import aggregate_capability
from model_capability_bench.suite import CapabilitySuiteBundle


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def consolidate_runs(
    *, sources: list[Path], output_dir: Path, run_id: str, run_group: str,
    suite: CapabilitySuiteBundle, plan_only: bool = False,
) -> dict[str, Any]:
    """Select by logical identity and terminal timestamp; never select by score."""
    output_dir = output_dir.resolve()
    if not run_id.strip() or not run_group.strip():
        raise ValueError("Consolidation needs non-empty run ID and group")
    if output_dir.exists():
        raise ValueError("Consolidation output already exists; choose a new run ID")
    source_paths = sorted({p.resolve() for p in sources})
    if not source_paths:
        raise ValueError("Consolidation requires source runs")
    selected: dict[tuple, dict] = {}
    provenance = []
    model_defs: dict[str, dict] = {}
    cap_defs: dict[str, dict] = {}
    identities: dict[tuple, tuple] = {}
    suite_identity = None
    source_ids: set[str] = set()
    for path in source_paths:
        if path == output_dir or path in output_dir.parents:
            raise ValueError("Consolidation output must be separate from its sources")
        manifest = json.loads((path / "run_manifest.json").read_text())
        source_id = manifest["run"]["run_id"]
        if source_id == run_id or source_id in source_ids:
            raise ValueError("Source run IDs must be unique and differ from output run ID")
        source_ids.add(source_id)
        identity = manifest["suite"]
        if suite_identity is not None and identity != suite_identity:
            raise ValueError("Source suite versions, profiles and seeds must match")
        suite_identity = identity
        checksums = {name: sha256_file(path / name) for name in (
            "run_manifest.json", "state.jsonl", "raw.jsonl", "evaluation.jsonl",
        )}
        provenance.append({"run_id": source_id, "checksums": checksums})
        for model in manifest["models"]:
            key = model["model_key"]
            if key in model_defs and model_defs[key]["model_signature"] != model["model_signature"]:
                raise ValueError("Cannot consolidate different artifacts under the same model key")
            model_defs[key] = model
        for cap in manifest["capabilities"]:
            key = cap["capability_id"]
            if key in cap_defs and any(cap_defs[key].get(k) != cap.get(k) for k in (
                "task_id", "dataset_ids", "metrics",
            )):
                raise ValueError("Source capability definitions must match")
            cap_defs[key] = cap
        raw = {(row["case_id"], row["attempt"]): row
               for row in read_jsonl_records(path / "raw.jsonl")}
        evaluations = {(row["case_id"], row["attempt"]): row
                       for row in read_jsonl_records(path / "evaluation.jsonl")}
        case_identities = {}
        for state in read_jsonl_records(path / "state.jsonl"):
            cid = state["case_id"]
            if "identity" in state:
                case_identities[cid] = state["identity"]
            case = case_identities.get(cid)
            if case is None:
                raise ValueError("Source state has no case identity")
            fields = (
                "model_key", "capability_id", "dataset_id", "dataset_revision",
                "dataset_split", "sample_id", "task_id", "task_version",
                "prompt_id", "prompt_version", "suite_id", "suite_version",
            )
            if any(not case.get(k) for k in fields):
                raise ValueError("Source case identity is incomplete")
            logical = tuple(case[k] for k in fields)
            semantic_key = (case["model_key"], case["capability_id"], case["dataset_id"])
            semantic = tuple(case[k] for k in (
                "dataset_revision", "dataset_split", "task_version", "prompt_id", "prompt_version",
            ))
            if semantic_key in identities and identities[semantic_key] != semantic:
                raise ValueError("Dataset revisions/splits and task/prompt versions must match")
            identities[semantic_key] = semantic
            rank = (datetime.fromisoformat(state["timestamp_utc"]), source_id,
                    int(state["attempt"]), cid)
            if logical not in selected or rank > selected[logical]["rank"]:
                selected[logical] = {
                    "rank": rank, "source_run_id": source_id, "state": state,
                    "identity": case, "raw": raw.get((cid, state["attempt"])),
                    "evaluation": evaluations.get((cid, state["attempt"])),
                }
        # A source changing while read cannot produce a reproducible snapshot.
        if any(sha256_file(path / name) != value for name, value in checksums.items()):
            raise ValueError("Source evidence changed during consolidation; stop the source run first")
    if not selected:
        raise ValueError("Source runs contain no cases")
    evidence = [selected[key] for key in sorted(selected)]
    for item in evidence:
        if item["state"]["status"] != "completed" or not item["raw"] or not item["evaluation"]:
            raise ValueError("Latest attempt is incomplete or lacks paired inference/evaluation evidence; recover it first")
    current_caps = {cap.spec.capability_id: cap.spec for cap in suite.resolved_capabilities}
    for key, cap in cap_defs.items():
        current = current_caps.get(key)
        if current is None or [
            {"name": m.name, "source": m.source, "reducer": m.reducer,
             "field": m.field, "primary": m.primary} for m in current.metrics
        ] != cap["metrics"]:
            raise ValueError("Current metric definitions differ from source; cannot recalculate safely")
    generation = sorted({json.dumps(item["identity"]["generation"], sort_keys=True) for item in evidence})
    invalid = sum(not item["raw"]["record"]["valid"] or not item["evaluation"]["record"]["valid"]
                  for item in evidence)
    summary = {
        "run_id": run_id, "run_group": run_group, "planned_cases": len(evidence),
        "completed_cases": len(evidence), "failed_cases": 0, "skipped_cases": 0,
        "model_failures": 0, "output_dir": str(output_dir),
        "invalid_cases": invalid, "failure_rate": invalid / len(evidence),
        "generation_configs": [json.loads(g) for g in generation],
        "mixed_generation": len(generation) > 1,
    }
    if plan_only:
        return summary
    now = datetime.now(UTC).isoformat()
    signatures = {"models": {}, "executions": {}, "benchmarks": {}}
    for key, model in model_defs.items():
        signatures["models"][key] = model["model_signature"]
        executions = sorted({item["raw"]["metadata"]["execution_signature"] for item in evidence
                             if item["identity"]["model_key"] == key})
        execution = executions[0] if len(executions) == 1 else "sha256:execution:" + _digest(executions)
        signatures["executions"][key] = execution
        model_defs[key] = {**model, "execution_signature": execution, "execution_metadata": {
            "runtime_source": "consolidated", "source_execution_signatures": executions,
        }}
    for cap in cap_defs:
        cap_cases = [item for item in evidence if item["identity"]["capability_id"] == cap]
        signatures["benchmarks"][cap] = "sha256:consolidated:" + _digest([
            {"identity": item["identity"], "source_run_id": item["source_run_id"],
             "case_id": item["state"]["case_id"], "attempt": item["state"]["attempt"]}
            for item in cap_cases
        ])
    metadata = {"experiment_kind": "consolidated", "selection_policy": "latest-attempt-v1",
                "sources": provenance, "signatures": signatures,
                "mixed_generation": summary["mixed_generation"],
                "generation_configs": summary["generation_configs"]}
    groups = defaultdict(list)
    for item in evidence:
        case = item["identity"]
        meta = {**item["state"]["metadata"], "run_id": run_id, "run_group": run_group,
                "benchmark_signature": signatures["benchmarks"][case["capability_id"]],
                "execution_signature": signatures["executions"][case["model_key"]],
                "consolidation_source": {
                    "run_id": item["source_run_id"], "case_id": item["state"]["case_id"],
                    "attempt": item["state"]["attempt"],
                    "timestamp_utc": item["state"]["timestamp_utc"],
                    "generation": case["generation"],
                    "benchmark_signature": item["state"]["metadata"]["benchmark_signature"],
                    "execution_signature": item["state"]["metadata"]["execution_signature"],
                }}
        for kind in ("raw", "evaluation"):
            row = copy.deepcopy(item[kind])
            row["metadata"] = meta
            row["record"].update({"run_id": run_id})
            if "run_group" in row["record"]:
                row["record"]["run_group"] = run_group
            item[kind] = row
        item["case_id"] = item["state"]["case_id"]
        item["attempt"] = item["state"]["attempt"]
        item["state"] = {**item["state"], "metadata": meta, "identity": case}
        groups[(case["model_key"], case["capability_id"])].append(item)
    aggregates = []
    indices = []
    for (model, cap), items in groups.items():
        records = aggregate_capability(current_caps[cap], items, model_key=model,
                                       run_id=run_id, run_group=run_group,
                                       profile=suite_identity["profile"])
        for record in records:
            record.update({"model_signature": signatures["models"][model],
                           "execution_signature": signatures["executions"][model],
                           "benchmark_signature": signatures["benchmarks"][cap]})
        aggregates.extend(records)
        indices.append({"run_id": run_id, "run_group": run_group, "model_key": model,
                        "capability_id": cap, "task_id": current_caps[cap].task_id,
                        "profile": suite_identity["profile"], "failure_count": 0,
                        "dataset_ids": list(current_caps[cap].dataset_ids),
                        "cases": [{"case_id": i["case_id"], "attempt": i["attempt"]} for i in items]})
    summary.update({"aggregate_count": len(aggregates), "metadata": metadata})
    manifest = {
        "schema_version": "1", "created_at_utc": now, "run": summary, "suite": suite_identity,
        "models": list(model_defs.values()), "capabilities": list(cap_defs.values()),
        "signatures": signatures, "configuration": {
            "configuration_id": "consolidated", "experiment_kind": "consolidated",
            "inference": {"mixed_generation": summary["mixed_generation"],
                          "generation_configs": summary["generation_configs"]},
        },
    }
    for cap in manifest["capabilities"]:
        cap["benchmark_signature"] = signatures["benchmarks"][cap["capability_id"]]
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".consolidate-", dir=output_dir.parent))
    try:
        def write_jsonl(name: str, rows: list) -> None:
            (staging / name).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        for kind in ("state", "raw", "evaluation"):
            write_jsonl(kind + ".jsonl", [item[kind] for item in evidence])
        write_jsonl("aggregates.jsonl", aggregates)
        write_jsonl("report_index.jsonl", indices)
        write_jsonl("events.jsonl", [{"event": "run_completed", "timestamp_utc": now,
                                     "metadata": {"run_id": run_id}}])
        (staging / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        # No single-machine or single-budget performance claim for a consolidated run.
        (staging / "environment.json").write_text(json.dumps({"consolidation": metadata}))
        staging.rename(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary
