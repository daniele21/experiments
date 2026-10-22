"""Select unsuccessful latest logical cases without rewriting source evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CaseSelection = tuple[str, str, str, str]


def select_error_cases(
    sources: list[Path], *, models: tuple[str, ...], capabilities: tuple[str, ...],
    profile: str, seed: int,
) -> tuple[tuple[CaseSelection, ...], dict[str, object]]:
    latest: dict[CaseSelection, dict] = {}
    provenance = []
    for source in sorted({path.resolve() for path in sources}):
        manifest = json.loads((source / "run_manifest.json").read_text())
        suite = manifest["suite"]
        if suite["profile"] != profile or suite["seed"] != seed:
            raise ValueError("Recovery must use the source profile and seed")
        state_bytes = (source / "state.jsonl").read_bytes()
        provenance.append({
            "run_id": manifest["run"]["run_id"],
            "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        })
        for line in state_bytes.decode().splitlines():
            row = json.loads(line)
            meta = row["metadata"]
            key = tuple(str(meta.get(k) or "") for k in (
                "model_key", "capability_id", "dataset_id", "sample_id",
            ))
            if key[0] not in models or key[1] not in capabilities:
                continue
            if not all(key):
                raise ValueError("Source case is missing recovery identity fields")
            previous = latest.get(key)
            if previous is None or row["timestamp_utc"] > previous["timestamp_utc"]:
                latest[key] = row
    selected = tuple(sorted(key for key, row in latest.items() if (
        row["status"] == "failed"
        or (row["status"] == "completed" and row["metadata"].get("valid") is False)
    )))
    if not selected:
        raise ValueError("No unsuccessful cases match the selected models/capabilities")
    return selected, {
        "experiment_kind": "recovery",
        "recovery_sources": provenance,
        "recovery_cases": [list(key) for key in selected],
    }
