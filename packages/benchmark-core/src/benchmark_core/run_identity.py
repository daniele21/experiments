from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RunIdentity:
    run_id: str
    run_group: str
    suite: str
    run_timestamp_utc: str
    runner_location: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("run_group", self.run_group),
            ("suite", self.suite),
            ("run_timestamp_utc", self.run_timestamp_utc),
            ("runner_location", self.runner_location),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")


def create_run_identity(
    *,
    run_group: str,
    suite: str,
    runner_location: str,
    run_id: str | None = None,
    run_timestamp_utc: str | None = None,
) -> RunIdentity:
    return RunIdentity(
        run_id=run_id or str(uuid.uuid4()),
        run_group=run_group,
        suite=suite,
        run_timestamp_utc=run_timestamp_utc or datetime.now(UTC).isoformat(),
        runner_location=runner_location,
    )
