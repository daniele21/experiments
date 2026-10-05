from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core import read_jsonl_records

from model_capability_bench.reporting.model import ReportCase


class ReportDataError(ValueError):
    """Raised when persisted benchmark evidence cannot form a report."""


def require_mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReportDataError(f"{context} must be an object")
    return value


def require_list(value: Any, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReportDataError(f"{context} must be a list")
    return value


def require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportDataError(f"{context} must be a non-empty string")
    return value


def _last_by(
    records: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, Any]]:
    selected: dict[tuple[str, ...], dict[str, Any]] = {}
    for record in records:
        key = tuple(str(record.get(field) or "") for field in key_fields)
        if any(not part for part in key):
            continue
        selected[key] = record
    return selected


class ReportEvidence:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        self._raw = self._index_exact("raw.jsonl")
        self._evaluations = self._index_exact("evaluation.jsonl")

    def manifest(self) -> Mapping[str, Any]:
        path = self.run_dir / "run_manifest.json"
        if not path.is_file():
            raise ReportDataError(f"Run manifest not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return require_mapping(payload, context="run manifest")

    def aggregates(
        self,
        run_id: str,
    ) -> dict[tuple[str, ...], dict[str, Any]]:
        records = [
            record
            for record in read_jsonl_records(self.run_dir / "aggregates.jsonl")
            if record.get("run_id") == run_id
        ]
        return _last_by(
            records,
            key_fields=("model_key", "capability_id", "metric"),
        )

    def report_indices(
        self,
        run_id: str,
    ) -> dict[tuple[str, ...], dict[str, Any]]:
        records = [
            record
            for record in read_jsonl_records(self.run_dir / "report_index.jsonl")
            if record.get("run_id") == run_id
        ]
        return _last_by(
            records,
            key_fields=("model_key", "capability_id"),
        )

    def events(self, run_id: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            record
            for record in read_jsonl_records(self.run_dir / "events.jsonl")
            if isinstance(record.get("metadata"), Mapping)
            and record["metadata"].get("run_id") == run_id
        )

    def case(self, case_id: str, attempt: int) -> ReportCase:
        key = (case_id, attempt)
        raw_item = self._raw.get(key)
        evaluation_item = self._evaluations.get(key)
        if raw_item is None or evaluation_item is None:
            raise ReportDataError(
                f"Report index references missing evidence for "
                f"{case_id!r} attempt {attempt}"
            )
        return self._report_case(
            case_id=case_id,
            attempt=attempt,
            raw_item=raw_item,
            evaluation_item=evaluation_item,
        )

    def _index_exact(self, filename: str) -> dict[tuple[str, int], dict[str, Any]]:
        indexed: dict[tuple[str, int], dict[str, Any]] = {}
        for item in read_jsonl_records(self.run_dir / filename):
            case_id = str(item.get("case_id") or "")
            attempt = int(item.get("attempt") or 0)
            if case_id and attempt > 0:
                indexed[(case_id, attempt)] = item
        return indexed

    @staticmethod
    def _report_case(
        *,
        case_id: str,
        attempt: int,
        raw_item: Mapping[str, Any],
        evaluation_item: Mapping[str, Any],
    ) -> ReportCase:
        raw_record = require_mapping(
            raw_item.get("record"),
            context="raw evidence record",
        )
        evaluation_record = require_mapping(
            evaluation_item.get("record"),
            context="evaluation evidence record",
        )
        raw_metadata = require_mapping(
            raw_record.get("metadata") or {},
            context="raw evidence metadata",
        )
        outer_metadata = require_mapping(
            raw_item.get("metadata") or {},
            context="raw evidence outer metadata",
        )

        latency_raw = raw_record.get("latency_ms")
        latency_ms = (
            float(latency_raw)
            if isinstance(latency_raw, int | float)
            and not isinstance(latency_raw, bool)
            else None
        )

        return ReportCase(
            case_id=case_id,
            attempt=attempt,
            sample_id=str(
                raw_metadata.get("sample_id")
                or outer_metadata.get("sample_id")
                or evaluation_record.get("sample_id")
                or ""
            ),
            dataset_id=str(
                raw_metadata.get("dataset_id")
                or outer_metadata.get("dataset_id")
                or ""
            ),
            expected=evaluation_record.get("expected"),
            prediction=evaluation_record.get("prediction"),
            inference_valid=bool(raw_record.get("valid")),
            evaluation_valid=bool(evaluation_record.get("valid")),
            latency_ms=latency_ms,
            family=(
                str(outer_metadata["case_family"])
                if outer_metadata.get("case_family")
                else None
            ),
            difficulty=(
                str(outer_metadata["difficulty"])
                if outer_metadata.get("difficulty")
                else None
            ),
            challenge_type=(
                str(outer_metadata["challenge_type"])
                if outer_metadata.get("challenge_type")
                else None
            ),
            metrics={
                str(metric.get("name")): metric.get("value")
                for metric in evaluation_record.get("metrics") or []
                if isinstance(metric, Mapping) and metric.get("name")
            },
            error_kind=(
                str(raw_record["error_kind"])
                if raw_record.get("error_kind")
                else None
            ),
            error_message=(
                str(raw_record["error_message"])
                if raw_record.get("error_message")
                else (
                    str(evaluation_record["error"])
                    if evaluation_record.get("error")
                    else None
                )
            ),
            normalized_output=raw_record.get("normalized_output"),
            raw_output=raw_record.get("raw_output"),
        )
