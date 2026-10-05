from __future__ import annotations

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.html_cases import render_case_details
from model_capability_bench.reporting.html_format import escape, format_value, json_text
from model_capability_bench.reporting.model import BenchmarkReport, ReportCell


def render_model_table(report: BenchmarkReport) -> str:
    rows = []
    for model in report.models:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(model.model_key)}</strong></td>"
            f"<td>{escape(model.model_id)}</td>"
            f"<td>{escape(model.effective_model_id)}</td>"
            f"<td>{escape(model.runtime_key)}</td>"
            f"<td>{escape(model.provider_key)}</td>"
            f"<td>{escape(model.deployment)}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Models</h2>"
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Model</th><th>Canonical ID</th><th>Runtime model ID</th>"
        "<th>Runtime</th><th>Provider</th><th>Deployment</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def render_primary_matrix(
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    header = "".join(
        f"<th>{escape(model.model_key)}</th>"
        for model in report.models
    )
    rows = []
    for capability in report.capabilities:
        by_model = {cell.model_key: cell for cell in capability.cells}
        cells = []
        for model in report.models:
            cell = by_model[model.model_key]
            value = format_value(
                cell.primary_value,
                config.numeric_precision,
            )
            cells.append(
                '<td class="metric-cell">'
                f'<div class="metric-value">{escape(value)}</div>'
                f'<div class="metric-name">{escape(cell.primary_metric)}</div>'
                f'<div class="metric-meta">n={cell.sample_count} · '
                f'failures={cell.failure_count}</div>'
                "</td>"
            )
        rows.append(
            "<tr>"
            f'<th class="row-head">{escape(capability.capability_id)}'
            f"<span>{escape(capability.task_id)}</span></th>"
            f"{''.join(cells)}</tr>"
        )

    return (
        "<section><h2>Primary capability matrix</h2>"
        '<p class="section-note">Each capability shows only its declared primary '
        "metric. Cells are intentionally not ranked or combined into an overall score.</p>"
        '<div class="table-wrap"><table class="matrix">'
        f"<thead><tr><th>Capability</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _secondary_metrics(
    cells: tuple[ReportCell, ...],
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    metric_names: list[str] = []
    for cell in cells:
        for metric_name in cell.metrics:
            if metric_name not in metric_names:
                metric_names.append(metric_name)

    header = "".join(
        f"<th>{escape(model.model_key)}</th>"
        for model in report.models
    )
    by_model = {cell.model_key: cell for cell in cells}
    rows = []
    for metric_name in metric_names:
        values = []
        for model in report.models:
            value = by_model[model.model_key].metrics.get(metric_name)
            values.append(
                f"<td>{escape(format_value(value, config.numeric_precision))}</td>"
            )
        rows.append(
            f'<tr><th class="row-head">{escape(metric_name)}</th>'
            f"{''.join(values)}</tr>"
        )
    if not rows:
        rows.append(
            f'<tr><td colspan="{len(report.models) + 1}">No aggregate metrics.</td></tr>'
        )

    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr><th>Metric</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _dimension_breakdown(
    cells: tuple[ReportCell, ...],
    report: BenchmarkReport,
    config: ReportingConfig,
    *,
    attribute: str,
    title: str,
) -> str:
    categories = sorted(
        {
            str(value)
            for cell in cells
            for case in cell.cases
            if (value := getattr(case, attribute)) is not None
        }
    )
    if not categories:
        return ""

    header = "".join(
        f"<th>{escape(model.model_key)}</th>"
        for model in report.models
    )
    by_model = {cell.model_key: cell for cell in cells}
    rows = []
    for category in categories:
        values = []
        for model in report.models:
            cell = by_model[model.model_key]
            scores = [
                float(value)
                for case in cell.cases
                if getattr(case, attribute) == category
                and (
                    value := case.metrics.get(cell.primary_metric)
                ) is not None
                and isinstance(value, (int, float, bool))
            ]
            if scores:
                mean = sum(scores) / len(scores)
                rendered = (
                    f"{format_value(mean, config.numeric_precision)} "
                    f"(n={len(scores)})"
                )
            else:
                rendered = "—"
            values.append(f"<td>{escape(rendered)}</td>")
        rows.append(
            f'<tr><th class="row-head">{escape(category)}</th>'
            f"{''.join(values)}</tr>"
        )

    return (
        f"<h3>{escape(title)}</h3>"
        '<div class="table-wrap"><table>'
        f"<thead><tr><th>{escape(attribute)}</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _paired_comparisons(
    capability,
    config: ReportingConfig,
) -> str:
    if not capability.comparisons:
        return ""

    rows = []
    for comparison in capability.comparisons:
        interval = "—"
        if comparison.ci95_low is not None and comparison.ci95_high is not None:
            interval = (
                f"[{format_value(comparison.ci95_low, config.numeric_precision)}, "
                f"{format_value(comparison.ci95_high, config.numeric_precision)}]"
            )
        practical = (
            format_value(comparison.practical_delta, config.numeric_precision)
            if comparison.practical_delta is not None
            else "—"
        )
        exceeds = (
            "yes"
            if comparison.exceeds_practical_delta is True
            else "no"
            if comparison.exceeds_practical_delta is False
            else "—"
        )
        rows.append(
            "<tr>"
            f"<td>{escape(comparison.model_a)}</td>"
            f"<td>{escape(comparison.model_b)}</td>"
            f"<td>{escape(comparison.metric)}</td>"
            f"<td>{comparison.paired_count}</td>"
            f"<td>{escape(format_value(comparison.delta_b_minus_a, config.numeric_precision))}</td>"
            f"<td>{escape(interval)}</td>"
            f"<td>{comparison.model_a_only}</td>"
            f"<td>{comparison.model_b_only}</td>"
            f"<td>{escape(format_value(comparison.mcnemar_exact_p, config.numeric_precision))}</td>"
            f"<td>{escape(practical)}</td>"
            f"<td>{escape(exceeds)}</td>"
            "</tr>"
        )

    return (
        "<h3>Paired model comparisons</h3>"
        '<p class="section-note">Delta is model B minus model A on the same sample IDs. '
        "Confidence intervals use a deterministic paired bootstrap; McNemar is shown "
        "for binary case outcomes.</p>"
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Model A</th><th>Model B</th><th>Metric</th><th>Paired n</th>"
        "<th>Δ B−A</th><th>95% CI</th><th>A only correct</th><th>B only correct</th>"
        "<th>McNemar p</th><th>Practical Δ</th><th>|Δ| ≥ practical?</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_capability_sections(
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    sections = []
    for capability in report.capabilities:
        datasets = ", ".join(capability.dataset_ids)
        details = "".join(
            render_case_details(cell, config)
            for cell in capability.cells
        )
        sections.append(
            "<section>"
            f"<h2>{escape(capability.capability_id)}</h2>"
            f'<p class="section-note">Task: {escape(capability.task_id)} · '
            f"Datasets: {escape(datasets)} · Primary metric: "
            f"{escape(capability.primary_metric)}</p>"
            f"{_secondary_metrics(capability.cells, report, config)}"
            f"{_paired_comparisons(capability, config)}"
            f"{_dimension_breakdown(capability.cells, report, config, attribute='family', title='Primary metric by family')}"
            f"{_dimension_breakdown(capability.cells, report, config, attribute='difficulty', title='Primary metric by difficulty')}"
            "<h3>Case drill-down</h3>"
            f"{details}</section>"
        )
    return "".join(sections)


def render_events(report: BenchmarkReport) -> str:
    rows = []
    for event in report.events:
        metadata = event.get("metadata")
        rows.append(
            "<tr>"
            f"<td>{escape(event.get('timestamp_utc') or '')}</td>"
            f"<td>{escape(event.get('event') or '')}</td>"
            f"<td>{escape(event.get('error_type') or '—')}</td>"
            f"<td>{escape(event.get('error_message') or '—')}</td>"
            f'<td><pre class="compact">{escape(json_text(metadata))}</pre></td>'
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">No run events recorded.</td></tr>')

    return (
        "<section><h2>Run events</h2>"
        '<p class="section-note">Infrastructure and lifecycle events are shown '
        "separately from model-quality evidence.</p>"
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Time</th><th>Event</th><th>Error type</th>"
        "<th>Error message</th><th>Metadata</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )
