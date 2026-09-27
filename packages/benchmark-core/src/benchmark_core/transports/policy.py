from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TransportPolicy:
    max_retries: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


def resolve_transport_policy(
    environ: Mapping[str, str],
    *,
    default_max_retries: int,
    default_timeout_seconds: float,
    max_retries_env: str = "BENCHMARK_MAX_RETRIES",
    timeout_env: str = "BENCHMARK_TIMEOUT_SECONDS",
) -> TransportPolicy:
    return TransportPolicy(
        max_retries=int(environ.get(max_retries_env, str(default_max_retries))),
        timeout_seconds=float(
            environ.get(timeout_env, str(default_timeout_seconds))
        ),
    )
