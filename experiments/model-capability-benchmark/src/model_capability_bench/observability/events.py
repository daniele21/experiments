from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from benchmark_core import to_jsonable


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class EvidenceRef:
    file: str
    case_id: str | None = None
    attempt: int | None = None

    def __post_init__(self) -> None:
        if not self.file.strip():
            raise ValueError("evidence reference file must not be empty")
        if self.attempt is not None and self.attempt <= 0:
            raise ValueError("evidence reference attempt must be > 0")


@dataclass(frozen=True)
class BenchmarkEvent:
    event_id: str
    event_type: str
    timestamp_utc: str
    run_id: str
    run_group: str | None = None
    schema_version: str = "1"
    model_key: str | None = None
    model_signature: str | None = None
    capability_id: str | None = None
    dataset_id: str | None = None
    sample_id: str | None = None
    case_id: str | None = None
    attempt: int | None = None
    benchmark_signature: str | None = None
    execution_signature: str | None = None
    status: str | None = None
    duration_ms: float | None = None
    payload_ref: EvidenceRef | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        if self.attempt is not None and self.attempt <= 0:
            raise ValueError("attempt must be > 0")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be >= 0")

    def to_record(self) -> dict[str, Any]:
        record = to_jsonable(self)
        record["event"] = self.event_type
        return record


def build_event(
    event_type: str,
    *,
    run_id: str,
    run_group: str | None = None,
    model_key: str | None = None,
    model_signature: str | None = None,
    capability_id: str | None = None,
    dataset_id: str | None = None,
    sample_id: str | None = None,
    case_id: str | None = None,
    attempt: int | None = None,
    benchmark_signature: str | None = None,
    execution_signature: str | None = None,
    status: str | None = None,
    duration_ms: float | None = None,
    payload_ref: EvidenceRef | None = None,
    metadata: Mapping[str, Any] | None = None,
    error: Exception | None = None,
) -> BenchmarkEvent:
    return BenchmarkEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp_utc=_now(),
        run_id=run_id,
        run_group=run_group,
        model_key=model_key,
        model_signature=model_signature,
        capability_id=capability_id,
        dataset_id=dataset_id,
        sample_id=sample_id,
        case_id=case_id,
        attempt=attempt,
        benchmark_signature=benchmark_signature,
        execution_signature=execution_signature,
        status=status,
        duration_ms=duration_ms,
        payload_ref=payload_ref,
        metadata=dict(metadata or {}),
        error_type=type(error).__name__ if error is not None else None,
        error_message=str(error) if error is not None else None,
    )
