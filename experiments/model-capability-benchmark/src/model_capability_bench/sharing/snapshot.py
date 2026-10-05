from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import sha256_file

from model_capability_bench.analytics.dashboard_export import export_dashboard_data


@dataclass(frozen=True)
class ShareSnapshotSummary:
    snapshot_id: str
    snapshot_path: str
    capability_id: str
    model_keys: tuple[str, ...]


def _portable_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root.resolve()))
    except ValueError:
        return resolved.name


def _snapshot_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def create_share_snapshot(
    *,
    results_root: Path,
    database_path: Path,
    capability_id: str,
    model_keys: tuple[str, ...],
    title: str | None = None,
) -> ShareSnapshotSummary:
    if not capability_id.strip():
        raise ValueError("capability_id must not be empty")
    if len(model_keys) < 1:
        raise ValueError("at least one model key is required")

    results_root = results_root.resolve()
    dashboard_dir = results_root / "analytics" / "dashboard"
    export_dashboard_data(
        database_path=database_path.resolve(),
        output_dir=dashboard_dir,
    )
    capability_path = dashboard_dir / "capabilities" / f"{capability_id}.json"
    if not capability_path.is_file():
        raise ValueError(
            f"Capability {capability_id!r} has no CURRENT dashboard payload"
        )

    capability = json.loads(capability_path.read_text(encoding="utf-8"))
    selected = set(model_keys)
    cells = [
        cell
        for cell in capability.get("cells") or []
        if cell.get("model_key") in selected
    ]
    found = {str(cell.get("model_key")) for cell in cells}
    missing = [model_key for model_key in model_keys if model_key not in found]
    if missing:
        raise ValueError(
            "Models missing from CURRENT capability payload: "
            + ", ".join(missing)
        )

    run_ids = sorted({str(cell["run_id"]) for cell in cells})
    benchmark_signatures = sorted(
        {str(cell["benchmark_signature"]) for cell in cells}
    )
    if len(benchmark_signatures) != 1:
        raise ValueError(
            "Share snapshots require one comparable benchmark signature"
        )

    comparison = capability.get("comparison")
    if isinstance(comparison, dict):
        comparison_models = {
            str(comparison.get("model_a") or ""),
            str(comparison.get("model_b") or ""),
        }
        if comparison_models != selected:
            comparison = None

    created_at = datetime.now(UTC).isoformat()
    core = {
        "schema_version": "1",
        "created_at_utc": created_at,
        "story_type": "result-comparison",
        "title": title or f"{capability_id}: model comparison",
        "capability_id": capability_id,
        "model_keys": list(model_keys),
        "model_signatures": [
            str(cell["model_signature"])
            for cell in cells
        ],
        "execution_signatures": [
            str(cell["execution_signature"])
            for cell in cells
        ],
        "run_ids": run_ids,
        "benchmark_signature": benchmark_signatures[0],
        "profile": cells[0].get("profile") if cells else None,
        "cells": cells,
        "comparison": comparison,
        "family_breakdown": [
            row
            for row in capability.get("family_breakdown") or []
            if row.get("model_key") in selected
        ],
        "methodology": {
            "paired_same_cases": comparison is not None,
            "source": "CURRENT projected benchmark evidence",
        },
        "sources": {
            "database": _portable_path(database_path, results_root),
            "capability_payload": _portable_path(
                capability_path,
                results_root,
            ),
            "capability_payload_sha256": sha256_file(capability_path),
        },
    }
    snapshot_id = _snapshot_id(core)
    payload = {
        **core,
        "snapshot_id": snapshot_id,
    }

    snapshot_dir = results_root / "shares" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    snapshot_path = snapshot_dir / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return ShareSnapshotSummary(
        snapshot_id=snapshot_id,
        snapshot_path=str(snapshot_path),
        capability_id=capability_id,
        model_keys=model_keys,
    )
