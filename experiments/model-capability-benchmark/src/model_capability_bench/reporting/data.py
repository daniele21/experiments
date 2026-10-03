from __future__ import annotations

from collections.abc import Mapping
from itertools import combinations
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
    ReportPairwiseComparison,
)
from model_capability_bench.runner.comparison import paired_binary_comparison


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


def _all_cases_for_index(
    evidence: ReportEvidence,
    report_index: Mapping[str, Any] | None,
) -> tuple[Any, ...]:
    if report_index is None:
        return ()

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
    return tuple(cases)


def _cases_for_index(
    evidence: ReportEvidence,
    report_index: Mapping[str, Any] | None,
    config: ReportingConfig,
) -> tuple[tuple[Any, ...], int]:
    if report_index is None:
        return (), 0

    cases = _all_cases_for_index(evidence, report_index)
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


def _comparison_metric_name(
    capability: Mapping[str, Any],
    metrics_config: list[Any],
) -> str | None:
    comparison = capability.get("comparison")
    if isinstance(comparison, Mapping):
        explicit = comparison.get("metric")
        if isinstance(explicit, str) and explicit.strip():
            return explicit
    for raw_metric in metrics_config:
        if not isinstance(raw_metric, Mapping) or raw_metric.get("primary") is not True:
            continue
        if raw_metric.get("source") != "task_metric":
            return None
        value = raw_metric.get("field") or raw_metric.get("name")
        return str(value) if value else None
    return None


def _comparison_practical_delta(
    capability: Mapping[str, Any],
) -> float | None:
    raw = capability.get("comparison")
    if not isinstance(raw, Mapping):
        return None
    value = raw.get("practical_delta")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _case_as_comparison_evidence(case: Any) -> dict[str, Any]:
    return {
        "state": {"metadata": {"sample_id": case.sample_id}},
        "evaluation": {
            "record": {
                "metrics": [
                    {"name": name, "value": value}
                    for name, value in case.metrics.items()
                ]
            }
        },
    }


def _pairwise_comparisons(
    *,
    capability: Mapping[str, Any],
    capability_id: str,
    models: tuple[ReportModelInfo, ...],
    report_indices: Mapping[tuple[str, ...], Mapping[str, Any]],
    evidence: ReportEvidence,
    metrics_config: list[Any],
) -> tuple[ReportPairwiseComparison, ...]:
    metric_name = _comparison_metric_name(capability, metrics_config)
    if metric_name is None:
        return ()

    practical_delta = _comparison_practical_delta(capability)
    cases_by_model = {
        model.model_key: _all_cases_for_index(
            evidence,
            report_indices.get((model.model_key, capability_id)),
        )
        for model in models
    }

    comparisons_out: list[ReportPairwiseComparison] = []
    for model_a, model_b in combinations(models, 2):
        result = paired_binary_comparison(
            [
                _case_as_comparison_evidence(case)
                for case in cases_by_model[model_a.model_key]
            ],
            [
                _case_as_comparison_evidence(case)
                for case in cases_by_model[model_b.model_key]
            ],
            metric_name=metric_name,
            practical_delta=practical_delta,
        )
        if int(result["paired_count"]) <= 0:
            continue
        comparisons_out.append(
            ReportPairwiseComparison(
                capability_id=capability_id,
                model_a=model_a.model_key,
                model_b=model_b.model_key,
                metric=metric_name,
                paired_count=int(result["paired_count"]),
                delta_b_minus_a=result["delta_b_minus_a"],
                ci95_low=result["ci95_low"],
                ci95_high=result["ci95_high"],
                both_correct=int(result["both_correct"]),
                model_a_only=int(result["model_a_only"]),
                model_b_only=int(result["model_b_only"]),
                both_wrong=int(result["both_wrong"]),
                mcnemar_exact_p=result["mcnemar_exact_p"],
                practical_delta=practical_delta,
                exceeds_practical_delta=result["exceeds_practical_delta"],
            )
        )
    return tuple(comparisons_out)


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
        metrics_config = require_list(
            capability.get("metrics"),
            context=f"manifest capability {index} metrics",
        )
        primary_metric = _primary_metric(
            capability_id,
            metrics_config,
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
                comparisons=_pairwise_comparisons(
                    capability=capability,
                    capability_id=capability_id,
                    models=models,
                    report_indices=report_indices,
                    evidence=evidence,
                    metrics_config=metrics_config,
                ),
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
