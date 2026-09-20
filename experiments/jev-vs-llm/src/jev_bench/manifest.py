from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

PACKAGES = ["jev-bench", "typesafe-sdk", "openai", "numpy", "pandas", "plotly", "typer"]


def _package_versions() -> dict[str, str]:
    result = {}
    for package in PACKAGES:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


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
    payload = {
        "run_group": run_group,
        "suite": suite,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "runner_location": runner_location,
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requested_models": requested_models,
        "resolved_models": resolved_models,
        "parameters": parameters,
        "pricing": pricing,
        "packages": _package_versions(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
