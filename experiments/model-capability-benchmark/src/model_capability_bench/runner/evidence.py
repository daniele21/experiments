from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import (
    EvaluationRecord,
    RawInferenceRecord,
    append_jsonl_record,
    read_jsonl_records,
    to_jsonable,
)

from model_capability_bench.observability import BenchmarkEvent, EvidenceRef, build_event


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class EvidenceStore:
    root: Path
    _latest_state: dict[str, dict[str, Any]] = field(
        init=False,
        default_factory=dict,
    )
    _attempts: dict[str, int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for record in read_jsonl_records(self.state_path):
            case_id = str(record.get("case_id") or "")
            attempt = int(record.get("attempt") or 0)
            if not case_id or attempt <= 0:
                continue
            self._attempts[case_id] = max(
                attempt,
                self._attempts.get(case_id, 0),
            )
            self._latest_state[case_id] = record

    @property
    def state_path(self) -> Path:
        return self.root / "state.jsonl"

    @property
    def raw_path(self) -> Path:
        return self.root / "raw.jsonl"

    @property
    def evaluation_path(self) -> Path:
        return self.root / "evaluation.jsonl"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def aggregates_path(self) -> Path:
        return self.root / "aggregates.jsonl"

    @property
    def report_index_path(self) -> Path:
        return self.root / "report_index.jsonl"

    def should_skip(self, case_id: str, *, retry_failures: bool) -> bool:
        state = self._latest_state.get(case_id)
        if state is None:
            return False
        status = state.get("status")
        if status == "completed":
            return True
        return status == "failed" and not retry_failures

    def record_typed_event(self, event: BenchmarkEvent) -> None:
        append_jsonl_record(event.to_record(), self.events_path)

    def record_stage_event(
        self,
        event_type: str,
        *,
        metadata: dict[str, Any],
        status: str | None = None,
        duration_ms: float | None = None,
        payload_ref: EvidenceRef | None = None,
        error: Exception | None = None,
    ) -> None:
        run_id = str(metadata.get("run_id") or "")
        if not run_id:
            raise ValueError("typed benchmark events require run_id metadata")
        self.record_typed_event(
            build_event(
                event_type,
                run_id=run_id,
                run_group=(
                    str(metadata["run_group"])
                    if metadata.get("run_group")
                    else None
                ),
                model_key=(
                    str(metadata["model_key"])
                    if metadata.get("model_key")
                    else None
                ),
                model_signature=(
                    str(metadata["model_signature"])
                    if metadata.get("model_signature")
                    else None
                ),
                capability_id=(
                    str(metadata["capability_id"])
                    if metadata.get("capability_id")
                    else None
                ),
                dataset_id=(
                    str(metadata["dataset_id"])
                    if metadata.get("dataset_id")
                    else None
                ),
                sample_id=(
                    str(metadata["sample_id"])
                    if metadata.get("sample_id")
                    else None
                ),
                case_id=(
                    str(metadata["case_id"])
                    if metadata.get("case_id")
                    else None
                ),
                attempt=(
                    int(metadata["attempt"])
                    if metadata.get("attempt")
                    else None
                ),
                benchmark_signature=(
                    str(metadata["benchmark_signature"])
                    if metadata.get("benchmark_signature")
                    else None
                ),
                execution_signature=(
                    str(metadata["execution_signature"])
                    if metadata.get("execution_signature")
                    else None
                ),
                status=status,
                duration_ms=duration_ms,
                payload_ref=payload_ref,
                metadata=metadata,
                error=error,
            )
        )

    def begin_case(
        self,
        case_id: str,
        *,
        identity: Any,
        metadata: dict[str, Any],
    ) -> int:
        attempt = self._attempts.get(case_id, 0) + 1
        self._attempts[case_id] = attempt
        record = {
            "case_id": case_id,
            "attempt": attempt,
            "status": "started",
            "timestamp_utc": _now(),
            "identity": to_jsonable(identity),
            "metadata": to_jsonable(metadata),
        }
        append_jsonl_record(record, self.state_path)
        self._latest_state[case_id] = record
        event_metadata = {**metadata, "case_id": case_id, "attempt": attempt}
        self.record_stage_event(
            "case.started",
            metadata=event_metadata,
            status="started",
        )
        return attempt

    def record_raw(
        self,
        case_id: str,
        attempt: int,
        record: RawInferenceRecord,
        *,
        metadata: dict[str, Any],
    ) -> None:
        append_jsonl_record(
            {
                "case_id": case_id,
                "attempt": attempt,
                "timestamp_utc": _now(),
                "metadata": metadata,
                "record": record,
            },
            self.raw_path,
        )

    def record_evaluation(
        self,
        case_id: str,
        attempt: int,
        record: EvaluationRecord,
        *,
        metadata: dict[str, Any],
    ) -> None:
        append_jsonl_record(
            {
                "case_id": case_id,
                "attempt": attempt,
                "timestamp_utc": _now(),
                "metadata": metadata,
                "record": record,
            },
            self.evaluation_path,
        )

    def complete_case(
        self,
        case_id: str,
        attempt: int,
        *,
        metadata: dict[str, Any],
    ) -> None:
        record = {
            "case_id": case_id,
            "attempt": attempt,
            "status": "completed",
            "timestamp_utc": _now(),
            "metadata": to_jsonable(metadata),
        }
        append_jsonl_record(record, self.state_path)
        self._latest_state[case_id] = record
        event_metadata = {**metadata, "case_id": case_id, "attempt": attempt}
        self.record_stage_event(
            "case.completed",
            metadata=event_metadata,
            status="completed",
        )

    def fail_case(
        self,
        case_id: str,
        attempt: int,
        *,
        stage: str,
        error: Exception,
        metadata: dict[str, Any],
    ) -> None:
        record = {
            "case_id": case_id,
            "attempt": attempt,
            "status": "failed",
            "stage": stage,
            "timestamp_utc": _now(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "metadata": to_jsonable(metadata),
        }
        append_jsonl_record(record, self.state_path)
        self._latest_state[case_id] = record
        event_metadata = {
            **metadata,
            "case_id": case_id,
            "attempt": attempt,
            "failure_stage": stage,
        }
        stage_event = {
            "request": "request.failed",
            "provider": "inference.failed",
            "evaluation": "evaluation.failed",
        }.get(stage, f"{stage}.failed")
        self.record_stage_event(
            stage_event,
            metadata=event_metadata,
            status="failed",
            error=error,
        )
        self.record_stage_event(
            "case.failed",
            metadata=event_metadata,
            status="failed",
            error=error,
        )

    def record_event(
        self,
        event: str,
        *,
        metadata: dict[str, Any],
        error: Exception | None = None,
    ) -> None:
        event_type = {
            "run_started": "run.started",
            "run_completed": "run.completed",
            "runtime_prepare_failed": "model.prepare.failed",
            "runtime_release_failed": "model.release.failed",
            "dataset_load_failed": "capability.failed",
        }.get(event, event.replace("_", "."))
        self.record_stage_event(
            event_type,
            metadata=metadata,
            status="failed" if error is not None else None,
            error=error,
        )

    def append_aggregate(self, record: dict[str, Any]) -> None:
        append_jsonl_record(record, self.aggregates_path)

    def append_report_index(self, record: dict[str, Any]) -> None:
        append_jsonl_record(record, self.report_index_path)

    def failed_states(self) -> list[dict[str, Any]]:
        return [
            state
            for state in self._latest_state.values()
            if state.get("status") == "failed"
        ]

    def completed_evidence(self) -> list[dict[str, Any]]:
        completed = {
            (
                case_id,
                int(state["attempt"]),
            )
            for case_id, state in self._latest_state.items()
            if state.get("status") == "completed"
        }
        raw = {
            (str(item["case_id"]), int(item["attempt"])): item
            for item in read_jsonl_records(self.raw_path)
            if (str(item.get("case_id")), int(item.get("attempt") or 0))
            in completed
        }
        evaluations = {
            (str(item["case_id"]), int(item["attempt"])): item
            for item in read_jsonl_records(self.evaluation_path)
            if (str(item.get("case_id")), int(item.get("attempt") or 0))
            in completed
        }

        evidence: list[dict[str, Any]] = []
        for key in sorted(completed):
            if key not in raw or key not in evaluations:
                continue
            evidence.append(
                {
                    "case_id": key[0],
                    "attempt": key[1],
                    "state": self._latest_state[key[0]],
                    "raw": raw[key],
                    "evaluation": evaluations[key],
                }
            )
        return evidence
