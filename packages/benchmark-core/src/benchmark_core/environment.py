from __future__ import annotations

import platform
import subprocess
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version


def package_versions(packages: Sequence[str]) -> dict[str, str]:
    """Resolve package versions without assuming a particular benchmark suite."""
    result: dict[str, str] = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def git_commit() -> str | None:
    """Return the current repository commit when git metadata is available."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def python_version() -> str:
    return platform.python_version()


def platform_name() -> str:
    return platform.platform()
