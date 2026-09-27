from __future__ import annotations

import html
import json
from typing import Any

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.model import (
    BenchmarkReport,
    ReportCase,
    ReportCell,
)


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _format_value(value: Any, precision: int) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{precision}f}".rstrip("0").rstrip(".")
    return str(value)


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    )


def _model_header(report: BenchmarkReport) -> str:
    rows = []
    for model in report.models:
        rows.append(
            "<tr>"
            f"<td><strong>{_escape(model.model_key)}</strong></td>"
            f"<td>{_escape(model.model_id)}</td>"
            f"<td>{_escape(model.effective_model_id)}</td>"
            f"<td>{_escape(model.runtime_key)}</td>"
            f"<td>{_escape(model.provider_key)}</td>"
            f"<td>{_escape(model.deployment)}</td>"
            "</tr>"
        )
    return (
        "<section><h2>Models</h2>"
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Model</th><th>Canonical ID</th><th>Runtime model ID</th>"
        "<th>Runtime</th><th>Provider</th><th>Deployment</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _primary_matrix(report: BenchmarkReport, config: ReportingConfig) -> str:
    header = "".join(
        f"<th>{_escape(model.model_key)}</th>"
        for model in report.models
    )
    rows = []
    for capability in report.capabilities:
        cells = []
        by_model = {cell.model_key: cell for cell in capability.cells}
        for model in report.models:
            cell = by_model[model.model_key]
            value = _format_value(cell.primary_value, config.numeric_precision)
            cells.append(
                '<td class="metric-cell">'
                f'<div class="metric-value">{_escape(value)}</div>'
                f'<div class="metric-name">{_escape(cell.primary_metric)}</div>'
                f'<div class="metric-meta">n={cell.sample_count} · '
                f'failures={cell.failure_count}</div>'
                "</td>"
            )
        rows.append(
            "<tr>"
            f"<th class=\"row-head\">{_escape(capability.capability_id)}"
            f"<span>{_escape(capability.task_id)}</span></th>"
            f"{''.join(cells)}</tr>"
        )

    return (
        "<section><h2>Primary capability matrix</h2>"
        "<p class=\"section-note\">Each capability shows only its declared primary "
        "metric. Cells are intentionally not ranked or combined into an overall score.</p>"
        '<div class="table-wrap"><table class="matrix">'
        f"<thead><tr><th>Capability</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _secondary_metrics(
    capability_id: str,
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
        f"<th>{_escape(model.model_key)}</th>"
        for model in report.models
    )
    by_model = {cell.model_key: cell for cell in cells}
    rows = []
    for metric_name in metric_names:
        values = []
        for model in report.models:
            value = by_model[model.model_key].metrics.get(metric_name)
            values.append(
                f"<td>{_escape(_format_value(value, config.numeric_precision))}</td>"
            )
        rows.append(
            f"<tr><th class=\"row-head\">{_escape(metric_name)}</th>"
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


def _case_row(case: ReportCase, precision: int) -> str:
    errors = " · ".join(
        part
        for part in (case.error_kind, case.error_message)
        if part
    )
    evidence = (
        "<details><summary>Evidence</summary>"
        "<div class=\"evidence-grid\">"
        "<div><h5>Normalized</h5>"
        f"<pre>{_escape(_json_text(case.normalized_output))}</pre></div>"
        "<div><h5>Raw</h5>"
        f"<pre>{_escape(_json_text(case.raw_output))}</pre></div>"
        "</div></details>"
    )
    return (
        "<tr>"
        f"<td>{_escape(case.sample_id)}</td>"
        f"<td>{_escape(case.dataset_id)}</td>"
        f"<td><code>{_escape(case.case_id[:18])}…</code><br>"
        f"<small>attempt {case.attempt}</small></td>"
        f"<td><pre class=\"compact\">{_escape(_json_text(case.expected))}</pre></td>"
        f"<td><pre class=\"compact\">{_escape(_json_text(case.prediction))}</pre></td>"
        f"<td>{_escape(_format_value(case.inference_valid, precision))}</td>"
        f"<td>{_escape(_format_value(case.evaluation_valid, precision))}</td>"
        f"<td>{_escape(_format_value(case.latency_ms, precision))}</td>"
        f"<td>{_escape(errors or '—')}</td>"
        f"<td>{evidence}</td>"
        "</tr>"
    )


def _case_details(cell: ReportCell, config: ReportingConfig) -> str:
    if not cell.cases:
        body = "<p>No indexed completed case evidence for this cell.</p>"
    else:
        rows = "".join(
            _case_row(case, config.numeric_precision)
            for case in cell.cases
        )
        truncation = (
            f"<p class=\"section-note\">{cell.truncated_case_count} additional "
            "indexed cases are omitted by reporting configuration.</p>"
            if cell.truncated_case_count
            else ""
        )
        body = (
            f"{truncation}"
            '<div class="table-wrap case-table"><table>'
            "<thead><tr><th>Sample</th><th>Dataset</th><th>Case</th>"
            "<th>Expected</th><th>Prediction</th><th>Inference valid</th>"
            "<th>Evaluation valid</th><th>Latency ms</th><th>Error</th>"
            "<th>Evidence</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )

    return (
        "<details class=\"model-details\">"
        f"<summary>{_escape(cell.model_key)} · n={cell.sample_count} · "
        f"failures={cell.failure_count}</summary>{body}</details>"
    )


def _capability_sections(
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    sections = []
    for capability in report.capabilities:
        datasets = ", ".join(capability.dataset_ids)
        details = "".join(
            _case_details(cell, config)
            for cell in capability.cells
        )
        sections.append(
            "<section>"
            f"<h2>{_escape(capability.capability_id)}</h2>"
            f"<p class=\"section-note\">Task: {_escape(capability.task_id)} · "
            f"Datasets: {_escape(datasets)} · Primary metric: "
            f"{_escape(capability.primary_metric)}</p>"
            f"{_secondary_metrics(capability.capability_id, capability.cells, report, config)}"
            "<h3>Case drill-down</h3>"
            f"{details}</section>"
        )
    return "".join(sections)


def _events(report: BenchmarkReport) -> str:
    rows = []
    for event in report.events:
        metadata = event.get("metadata")
        rows.append(
            "<tr>"
            f"<td>{_escape(event.get('timestamp_utc') or '')}</td>"
            f"<td>{_escape(event.get('event') or '')}</td>"
            f"<td>{_escape(event.get('error_type') or '—')}</td>"
            f"<td>{_escape(event.get('error_message') or '—')}</td>"
            f"<td><pre class=\"compact\">{_escape(_json_text(metadata))}</pre></td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">No run events recorded.</td></tr>')

    return (
        "<section><h2>Run events</h2>"
        "<p class=\"section-note\">Infrastructure and lifecycle events are shown "
        "separately from model-quality evidence.</p>"
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Time</th><th>Event</th><th>Error type</th>"
        "<th>Error message</th><th>Metadata</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def render_html_report(
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(report.title)}</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #f7f7f8;
  --panel: #ffffff;
  --text: #171719;
  --muted: #65656d;
  --line: #dedee3;
  --soft: #f0f0f3;
  --accent: #2d4c7c;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #111114;
    --panel: #19191d;
    --text: #f3f3f4;
    --muted: #aaaab2;
    --line: #33333a;
    --soft: #232329;
    --accent: #9ebce7;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{ max-width: 1500px; margin: 0 auto; padding: 32px 24px 80px; }}
header, section {{
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 14px; padding: 24px; margin-bottom: 18px;
}}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
h2 {{ margin: 0 0 12px; font-size: 20px; }}
h3 {{ margin: 22px 0 10px; font-size: 16px; }}
h5 {{ margin: 0 0 6px; }}
.meta, .section-note {{ color: var(--muted); }}
.meta {{ display: flex; flex-wrap: wrap; gap: 10px 22px; }}
.note {{
  border-left: 3px solid var(--accent); padding: 10px 12px;
  background: var(--soft); margin-top: 18px;
}}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; min-width: 720px; }}
th, td {{
  border-bottom: 1px solid var(--line); padding: 10px 12px;
  text-align: left; vertical-align: top;
}}
thead th {{ background: var(--soft); position: sticky; top: 0; }}
.row-head span {{
  display: block; color: var(--muted); font-weight: 400; font-size: 12px;
}}
.metric-cell {{ min-width: 160px; }}
.metric-value {{ font-size: 20px; font-weight: 700; }}
.metric-name, .metric-meta {{ color: var(--muted); font-size: 12px; }}
.model-details {{
  border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 12px; margin: 8px 0;
}}
summary {{ cursor: pointer; font-weight: 650; }}
pre {{
  white-space: pre-wrap; overflow-wrap: anywhere; max-width: 620px;
  padding: 10px; border-radius: 8px; background: var(--soft);
}}
pre.compact {{ margin: 0; padding: 6px; max-height: 140px; overflow: auto; }}
.evidence-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px; margin-top: 10px;
}}
.case-table {{ margin-top: 10px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
</style>
</head>
<body>
<main>
<header>
  <h1>{_escape(report.title)}</h1>
  <div class="meta">
    <span><strong>Run:</strong> {_escape(report.run_id)}</span>
    <span><strong>Group:</strong> {_escape(report.run_group)}</span>
    <span><strong>Suite:</strong> {_escape(report.suite_id)} v{_escape(report.suite_version)}</span>
    <span><strong>Profile:</strong> {_escape(report.profile)}</span>
    <span><strong>Generated:</strong> {_escape(report.generated_at_utc)}</span>
  </div>
  <div class="note">{_escape(report.cost_semantics)}</div>
</header>
{_model_header(report)}
{_primary_matrix(report, config)}
{_capability_sections(report, config)}
{_events(report)}
</main>
</body>
</html>
"""
