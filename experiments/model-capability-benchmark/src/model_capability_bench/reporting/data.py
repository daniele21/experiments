from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.evidence import (
    ReportDataError,
    ReportEvidence,
    require_list,
    require_mapping,
    require_text,
)
from model_capability_bench.reporting.model import (
    BenchmarkReport,
    CapabilityReport,
    ReportCell,
    ReportModelInfo,
)


def _models(manifest: Mapping[str, Any]) -> tuple[ReportModelInfo, ...]:
    entries = require_list(manifest.get("models"), context="manifest models")
    models: list[ReportModelInfo] = []
    for index, raw_model in enumerate(entries):
        model = require_mapping(raw_model, context=f"manifest model {index}")
        models.append(
            ReportModelInfo(
                model_key=require_text(
                    model.get("model_key"),
                    context=f"manifest model {index} model_key",
                ),
                model_id=require_text(
                    model.get("model_id"),
                    context=f"manifest model {index} model_id",
                ),
                effective_model_id=require_text(
                    model.get("effective_model_id"),
                    context=f"manifest model {index} effective_model_id",
                ),
                runtime_key=require_text(
                    model.get("runtime_key"),
                    context=f"manifest model {index} runtime_key",
                ),
                provider_key=require_text(
                    model.get("provider_key"),
                    context=f"manifest model {index} provider_key",
                ),
                deployment=require_text(
                    model.get("deployment"),
                    context=f"manifest model {index} deployment",
                ),
            )
        )
    return tuple(models)


def _primary_metric(
    capability_id: str,
    metrics_config: list[Any],
) -> str:
    primary = [
        require_mapping(metric, context="manifest capability metric")
        for metric in metrics_config
        if isinstance(metric, Mapping) and metric.get("primary") is True
    ]
    if len(primary) != 1:
        raise ReportDataError(
            f"Capability {capability_id!r} must declare exactly one primary metric"
        )
    return require_text(
        primary[0].get("name"),
        context=f"capability {capability_id!r} primary metric",
    )


def _cases_for_index(
    evidence: ReportEvidence,
    report_index: Mapping[str, Any] | None,
    config: ReportingConfig,
) -> tuple[tuple[Any, ...], int]:
    if report_index is None:
        return (), 0

    indexed_cases = require_list(
        report_index.get("cases") or [],
        context="report index cases",
    )
    cases = []
    for raw_ref in indexed_cases:
        ref = require_mapping(raw_ref, context="report index case")
        case_id = require_text(
            ref.get("case_id"),
            context="report index case_id",
        )
        attempt = int(ref.get("attempt") or 0)
        if attempt <= 0:
            raise ReportDataError(
                f"Invalid attempt for report case {case_id!r}"
            )
        cases.append(evidence.case(case_id, attempt))

    visible = tuple(cases[: config.max_case_rows_per_cell])
    return visible, max(0, len(cases) - len(visible))


def _cell(
    *,
    model: ReportModelInfo,
    capability_id: str,
    task_id: str,
    dataset_ids: tuple[str, ...],
    primary_metric: str,
    aggregates: Mapping[tuple[str, ...], Mapping[str, Any]],
    report_indices: Mapping[tuple[str, ...], Mapping[str, Any]],
    evidence: ReportEvidence,
    config: ReportingConfig,
) -> ReportCell:
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
    report_index = report_indices.get((model.model_key, capability_id))
    cases, truncated_count = _cases_for_index(
        evidence,
        report_index,
        config,
    )

    if report_index is not None:
        indexed_dataset_ids = tuple(
            str(value)
            for value in require_list(
                report_index.get("dataset_ids") or [],
                context="report index dataset_ids",
            )
        )
        failure_count = int(report_index.get("failure_count") or 0)
    else:
        indexed_dataset_ids = dataset_ids
        failure_count = 0

    sample_count = len(cases) + truncated_count
    if primary_record is not None:
        sample_count = int(primary_record.get("sample_count") or 0)
        failure_count = int(
            primary_record.get("failure_count") or failure_count
        )

    return ReportCell(
        model_key=model.model_key,
        capability_id=capability_id,
        task_id=task_id,
        primary_metric=primary_metric,
        metrics=metric_values,
        sample_count=sample_count,
        failure_count=failure_count,
        dataset_ids=indexed_dataset_ids,
        cases=cases,
        truncated_case_count=truncated_count,
    )


def _capabilities(
    manifest: Mapping[str, Any],
    *,
    models: tuple[ReportModelInfo, ...],
    aggregates: Mapping[tuple[str, ...], Mapping[str, Any]],
    report_indices: Mapping[tuple[str, ...], Mapping[str, Any]],
    evidence: ReportEvidence,
    config: ReportingConfig,
) -> tuple[CapabilityReport, ...]:
    entries = require_list(
        manifest.get("capabilities"),
        context="manifest capabilities",
    )
    result: list[CapabilityReport] = []
    for index, raw_capability in enumerate(entries):
        capability = require_mapping(
            raw_capability,
            context=f"manifest capability {index}",
        )
        capability_id = require_text(
            capability.get("capability_id"),
            context=f"manifest capability {index} capability_id",
        )
        task_id = require_text(
            capability.get("task_id"),
            context=f"manifest capability {index} task_id",
        )
        dataset_ids = tuple(
            str(value)
            for value in require_list(
                capability.get("dataset_ids"),
                context=f"manifest capability {index} dataset_ids",
            )
        )
        primary_metric = _primary_metric(
            capability_id,
            require_list(
                capability.get("metrics"),
                context=f"manifest capability {index} metrics",
            ),
        )
        cells = tuple(
            _cell(
                model=model,
                capability_id=capability_id,
                task_id=task_id,
                dataset_ids=dataset_ids,
                primary_metric=primary_metric,
                aggregates=aggregates,
                report_indices=report_indices,
                evidence=evidence,
                config=config,
            )
            for model in models
        )
        result.append(
            CapabilityReport(
                capability_id=capability_id,
                task_id=task_id,
                dataset_ids=dataset_ids,
                primary_metric=primary_metric,
                cells=cells,
            )
        )
    return tuple(result)


def load_benchmark_report(
    run_dir: Path,
    config: ReportingConfig,
) -> BenchmarkReport:
    evidence = ReportEvidence(run_dir)
    manifest = evidence.manifest()
    run = require_mapping(manifest.get("run"), context="manifest run")
    suite = require_mapping(manifest.get("suite"), context="manifest suite")

    run_id = require_text(run.get("run_id"), context="manifest run.run_id")
    models = _models(manifest)
    aggregates = evidence.aggregates(run_id)
    report_indices = evidence.report_indices(run_id)

    return BenchmarkReport(
        title=config.title,
        run_id=run_id,
        run_group=require_text(
            run.get("run_group"),
            context="manifest run.run_group",
        ),
        suite_id=require_text(
            suite.get("suite_id"),
            context="manifest suite.suite_id",
        ),
        suite_version=require_text(
            suite.get("version"),
            context="manifest suite.version",
        ),
        profile=require_text(
            suite.get("profile"),
            context="manifest suite.profile",
        ),
        generated_at_utc=datetime.now(UTC).isoformat(),
        models=models,
        capabilities=_capabilities(
            manifest,
            models=models,
            aggregates=aggregates,
            report_indices=report_indices,
            evidence=evidence,
            config=config,
        ),
        events=evidence.events(run_id),
    )
