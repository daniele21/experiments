from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from benchmark_core import load_yaml_section


@dataclass(frozen=True)
class RunnerDefaults:
    output_root: Path
    cache_dir: Path
    default_profile: str
    default_seed: int
    resume: bool
    retry_failures: bool

    def __post_init__(self) -> None:
        if not self.default_profile.strip():
            raise ValueError("default_profile must not be empty")


def load_runner_defaults(root: Path) -> RunnerDefaults:
    raw = load_yaml_section(
        root / "runner.yaml",
        "runner",
        required=True,
    )
    allowed = {
        "output_root",
        "cache_dir",
        "default_profile",
        "default_seed",
        "resume",
        "retry_failures",
    }
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise ValueError(
            "runner config contains unsupported fields: "
            + ", ".join(unknown)
        )

    return RunnerDefaults(
        output_root=root / str(raw["output_root"]),
        cache_dir=root / str(raw["cache_dir"]),
        default_profile=str(raw["default_profile"]),
        default_seed=int(raw["default_seed"]),
        resume=bool(raw["resume"]),
        retry_failures=bool(raw["retry_failures"]),
    )
