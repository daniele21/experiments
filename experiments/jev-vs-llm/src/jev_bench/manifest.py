from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmark_core.manifests import write_environment_manifest

PACKAGES = ["jev-bench", "typesafe-sdk", "openai", "numpy", "pandas", "plotly", "typer"]


def write_manifest(
    path: Path,
    *,
    run_group: str,
    suite: str,
    runner_location: str,
    requested_models: dict[str, Any],
    resolved_models: dict[str, list[str]],
    parameters: dict[str, Any],
    pricing: dict[str, Any],
) -> None:
    """Compatibility wrapper around the shared benchmark manifest writer."""
    write_environment_manifest(
        path,
        run_group=run_group,
        suite=suite,
        runner_location=runner_location,
        requested_models=requested_models,
        resolved_models=resolved_models,
        parameters=parameters,
        pricing=pricing,
        packages=PACKAGES,
    )
