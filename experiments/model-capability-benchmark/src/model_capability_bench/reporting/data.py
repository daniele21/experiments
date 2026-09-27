from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark_core import read_jsonl_records

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.model import (
    BenchmarkReport,
    CapabilityReport,
    ReportCase,
    ReportCell,
    ReportModelInfo,
)


class ReportDataError(ValueError):
    """Raised when persisted benchmark evidence cannot form a report."""


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReportDataError(f"{context} must be an object")
    return value


def _list(value: Any, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReportDataError(f"{context} must be a list")
    return value


def _text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportDataError(f"{context} must be a non-empty string")
    return value


def _manifest(run_dir: Path) -> Mapping[str, Any]:
    path = run_dir / "run_manifest.json"
    if not path.is_file():
        raise ReportDataError(f"Run manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(payload, context="run manifest")


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


def _indexed_evidence(
    run_dir: Path,
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    raw: dict[tuple[str, int], dict[str, Any]] = {}
    for item in read_jsonl_records(run_dir / "raw.jsonl"):
        case_id = str(item.get("case_id") or "")
        attempt = int(item.get("attempt") or 0)
        if case_id and attempt > 0:
            raw[(case_id, attempt)] = item

    evaluations: dict[tuple[str, int], dict[str, Any]] = {}
    for item in read_jsonl_records(run_dir / "evaluation.jsonl"):
        case_id = str(item.get("case_id") or "")
        attempt = int(item.get("attempt") or 0)
        if case_id and attempt > 0:
            evaluations[(case_id, attempt)] = item
    return raw, evaluations


def _report_case(
    *,
    case_id: str,
    attempt: int,
    raw_item: Mapping[str, Any],
    evaluation_item: Mapping[str, Any],
) -> ReportCase:
    raw_record = _mapping(raw_item.get("record"), context="raw evidence record")
    evaluation_record = _mapping(
        evaluation_item.get("record"),
        context="evaluation evidence record",
    )
    raw_metadata = _mapping(
        raw_record.get("metadata") or {},
        context="raw evidence metadata",
    )
    outer_metadata = _mapping(
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


def load_benchmark_report(
    run_dir: Path,
    config: ReportingConfig,
) -> BenchmarkReport:
    run_dir = run_dir.resolve()
    manifest = _manifest(run_dir)

    run = _mapping(manifest.get("run"), context="manifest run")
    suite = _mapping(manifest.get("suite"), context="manifest suite")
    run_id = _text(run.get("run_id"), context="manifest run.run_id")
    run_group = _text(run.get("run_group"), context="manifest run.run_group")
    suite_id = _text(suite.get("suite_id"), context="manifest suite.suite_id")
    suite_version = _text(suite.get("version"), context="manifest suite.version")
    profile = _text(suite.get("profile"), context="manifest suite.profile")

    model_entries = _list(manifest.get("models"), context="manifest models")
    models: list[ReportModelInfo] = []
    for index, raw_model in enumerate(model_entries):
        model = _mapping(raw_model, context=f"manifest model {index}")
        models.append(
            ReportModelInfo(
                model_key=_text(
                    model.get("model_key"),
                    context=f"manifest model {index} model_key",
                ),
                model_id=_text(
                    model.get("model_id"),
                    context=f"manifest model {index} model_id",
                ),
                effective_model_id=_text(
                    model.get("effective_model_id"),
                    context=f"manifest model {index} effective_model_id",
                ),
                runtime_key=_text(
                    model.get("runtime_key"),
                    context=f"manifest model {index} runtime_key",
                ),
                provider_key=_text(
                    model.get("provider_key"),
                    context=f"manifest model {index} provider_key",
                ),
                deployment=_text(
                    model.get("deployment"),
                    context=f"manifest model {index} deployment",
                ),
            )
        )

    aggregate_records = [
        record
        for record in read_jsonl_records(run_dir / "aggregates.jsonl")
        if record.get("run_id") == run_id
    ]
    aggregates = _last_by(
        aggregate_records,
        key_fields=("model_key", "capability_id", "metric"),
    )

    index_records = [
        record
        for record in read_jsonl_records(run_dir / "report_index.jsonl")
        if record.get("run_id") == run_id
    ]
    report_indices = _last_by(
        index_records,
        key_fields=("model_key", "capability_id"),
    )
    raw_by_case, evaluation_by_case = _indexed_evidence(run_dir)

    capability_entries = _list(
        manifest.get("capabilities"),
        context="manifest capabilities",
    )
    capabilities: list[CapabilityReport] = []
    for index, raw_capability in enumerate(capability_entries):
        capability = _mapping(
            raw_capability,
            context=f"manifest capability {index}",
        )
        capability_id = _text(
            capability.get("capability_id"),
            context=f"manifest capability {index} capability_id",
        )
        task_id = _text(
            capability.get("task_id"),
            context=f"manifest capability {index} task_id",
        )
        dataset_ids = tuple(
            str(value)
            for value in _list(
                capability.get("dataset_ids"),
                context=f"manifest capability {index} dataset_ids",
            )
        )
        metrics_config = _list(
            capability.get("metrics"),
            context=f"manifest capability {index} metrics",
        )
        primary_metrics = [
            _mapping(metric, context="manifest capability metric")
            for metric in metrics_config
            if isinstance(metric, Mapping) and metric.get("primary") is True
        ]
        if len(primary_metrics) != 1:
            raise ReportDataError(
                f"Capability {capability_id!r} must declare exactly one primary metric"
            )
        primary_metric = _text(
            primary_metrics[0].get("name"),
            context=f"capability {capability_id!r} primary metric",
        )

        cells: list[ReportCell] = []
        for model in models:
            metric_records = {
                key[2]: value
                for key, value in aggregates.items()
                if key[0] == model.model_key and key[1] == capability_id
            }
            metric_values = {
                metric_name: record.get("value")
                for metric_name, record in metric_records.items()
            }
            primary_record = metric_records.get(primary_metric)
            report_index = report_indices.get(
                (model.model_key, capability_id),
            )

            exact_cases: list[ReportCase] = []
            if report_index is not None:
                indexed_cases = _list(
                    report_index.get("cases") or [],
                    context=(
                        f"report index {model.model_key!r}/"
                        f"{capability_id!r} cases"
                    ),
                )
                for case_ref in indexed_cases:
                    ref = _mapping(case_ref, context="report index case")
                    case_id = _text(
                        ref.get("case_id"),
                        context="report index case_id",
                    )
                    attempt = int(ref.get("attempt") or 0)
                    if attempt <= 0:
                        raise ReportDataError(
                            f"Invalid attempt for report case {case_id!r}"
                        )
                    key = (case_id, attempt)
                    raw_item = raw_by_case.get(key)
                    evaluation_item = evaluation_by_case.get(key)
                    if raw_item is None or evaluation_item is None:
                        raise ReportDataError(
                            f"Report index references missing evidence for "
                            f"{case_id!r} attempt {attempt}"
                        )
                    exact_cases.append(
                        _report_case(
                            case_id=case_id,
                            attempt=attempt,
                            raw_item=raw_item,
                            evaluation_item=evaluation_item,
                        )
                    )

            visible_cases = tuple(
                exact_cases[: config.max_case_rows_per_cell]
            )
            truncated_count = max(
                0,
                len(exact_cases) - len(visible_cases),
            )
            cell_dataset_ids = (
                tuple(str(value) for value in report_index.get("dataset_ids", []))
                if report_index is not None
                else dataset_ids
            )
            sample_count = (
                int(primary_record.get("sample_count") or 0)
                if primary_record is not None
                else len(exact_cases)
            )
            failure_count = (
                int(primary_record.get("failure_count") or 0)
                if primary_record is not None
                else int(
                    report_index.get("failure_count") or 0
                    if report_index is not None
                    else 0
                )
            )
            cells.append(
                ReportCell(
                    model_key=model.model_key,
                    capability_id=capability_id,
                    task_id=task_id,
                    primary_metric=primary_metric,
                    metrics=metric_values,
                    sample_count=sample_count,
                    failure_count=failure_count,
                    dataset_ids=cell_dataset_ids,
                    cases=visible_cases,
                    truncated_case_count=truncated_count,
                )
            )

        capabilities.append(
            CapabilityReport(
                capability_id=capability_id,
                task_id=task_id,
                dataset_ids=dataset_ids,
                primary_metric=primary_metric,
                cells=tuple(cells),
            )
        )

    events = tuple(
        record
        for record in read_jsonl_records(run_dir / "events.jsonl")
        if isinstance(record.get("metadata"), Mapping)
        and record["metadata"].get("run_id") == run_id
    )

    return BenchmarkReport(
        title=config.title,
        run_id=run_id,
        run_group=run_group,
        suite_id=suite_id,
        suite_version=suite_version,
        profile=profile,
        generated_at_utc=datetime.now(UTC).isoformat(),
        models=tuple(models),
        capabilities=tuple(capabilities),
        events=events,
    )
