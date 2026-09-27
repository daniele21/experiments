from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core.environment import (
    git_commit,
    package_versions,
    platform_name,
    python_version,
)


def write_environment_manifest(
    path: Path,
    *,
    run_group: str,
    suite: str,
    runner_location: str,
    requested_models: Mapping[str, Any],
    resolved_models: Mapping[str, Sequence[str]],
    parameters: Mapping[str, Any],
    pricing: Mapping[str, Any],
    packages: Sequence[str] = (),
    created_at_utc: str | None = None,
    git_commit_sha: str | None = None,
    python: str | None = None,
    platform_value: str | None = None,
) -> None:
    """Write the environment/provenance envelope used by benchmark runs.

    The function intentionally accepts suite-specific parameters as opaque mappings.
    Task/model/dataset typed manifests can evolve on top without coupling this low-level
    serialization primitive to a particular experiment.
    """
    payload = {
        "run_group": run_group,
        "suite": suite,
        "created_at_utc": created_at_utc or datetime.now(UTC).isoformat(),
        "runner_location": runner_location,
        "git_commit": git_commit_sha if git_commit_sha is not None else git_commit(),
        "python": python or python_version(),
        "platform": platform_value or platform_name(),
        "requested_models": dict(requested_models),
        "resolved_models": {
            str(provider): list(models)
            for provider, models in resolved_models.items()
        },
        "parameters": dict(parameters),
        "pricing": dict(pricing),
        "packages": package_versions(packages),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
