from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

ResultState = Literal[
    "CURRENT",
    "HISTORICAL",
    "STALE",
    "NON_COMPARABLE",
    "PARTIAL",
]


@dataclass(frozen=True)
class ResultCandidate:
    run_id: str
    model_signature: str
    benchmark_signature: str
    capability_id: str
    completed_at_utc: str
    status: str
    execution_signature: str | None = None

    @property
    def quality_key(self) -> tuple[str, str, str]:
        return (
            self.model_signature,
            self.benchmark_signature,
            self.capability_id,
        )

    @property
    def performance_key(self) -> tuple[str, str, str, str | None]:
        return (
            self.model_signature,
            self.benchmark_signature,
            self.capability_id,
            self.execution_signature,
        )

    @property
    def is_valid_completed(self) -> bool:
        return self.status == "COMPLETED"


def canonical_latest(
    candidates: Sequence[ResultCandidate],
    *,
    performance: bool = False,
) -> dict[tuple[str, ...], ResultCandidate]:
    latest: dict[tuple[str, ...], ResultCandidate] = {}
    for candidate in candidates:
        if not candidate.is_valid_completed:
            continue
        key = (
            candidate.performance_key
            if performance
            else candidate.quality_key
        )
        previous = latest.get(key)
        if previous is None or (
            candidate.completed_at_utc,
            candidate.run_id,
        ) > (
            previous.completed_at_utc,
            previous.run_id,
        ):
            latest[key] = candidate
    return latest


def result_state(
    candidate: ResultCandidate,
    *,
    current: ResultCandidate | None,
    comparable: bool = True,
    stale: bool = False,
) -> ResultState:
    if candidate.status != "COMPLETED":
        return "PARTIAL"
    if not comparable:
        return "NON_COMPARABLE"
    if stale:
        return "STALE"
    if current is not None and current.run_id == candidate.run_id:
        return "CURRENT"
    return "HISTORICAL"
