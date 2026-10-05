from __future__ import annotations

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.html_format import escape, format_value, json_text
from model_capability_bench.reporting.model import ReportCase, ReportCell


def _case_row(case: ReportCase, precision: int) -> str:
    errors = " · ".join(
        part
        for part in (case.error_kind, case.error_message)
        if part
    )
    evidence = (
        "<details><summary>Evidence</summary>"
        '<div class="evidence-grid">'
        "<div><h5>Normalized</h5>"
        f"<pre>{escape(json_text(case.normalized_output))}</pre></div>"
        "<div><h5>Raw</h5>"
        f"<pre>{escape(json_text(case.raw_output))}</pre></div>"
        "</div></details>"
    )
    return (
        "<tr>"
        f"<td>{escape(case.sample_id)}</td>"
        f"<td>{escape(case.dataset_id)}</td>"
        f"<td>{escape(case.family or '—')}</td>"
        f"<td>{escape(case.difficulty or '—')}</td>"
        f"<td><code>{escape(case.case_id[:18])}…</code><br>"
        f"<small>attempt {case.attempt}</small></td>"
        f'<td><pre class="compact">{escape(json_text(case.expected))}</pre></td>'
        f'<td><pre class="compact">{escape(json_text(case.prediction))}</pre></td>'
        f"<td>{escape(format_value(case.inference_valid, precision))}</td>"
        f"<td>{escape(format_value(case.evaluation_valid, precision))}</td>"
        f"<td>{escape(format_value(case.latency_ms, precision))}</td>"
        f"<td>{escape(errors or '—')}</td>"
        f"<td>{evidence}</td>"
        "</tr>"
    )


def render_case_details(
    cell: ReportCell,
    config: ReportingConfig,
) -> str:
    if not cell.cases:
        body = "<p>No indexed completed case evidence for this cell.</p>"
    else:
        rows = "".join(
            _case_row(case, config.numeric_precision)
            for case in cell.cases
        )
        truncation = (
            f'<p class="section-note">{cell.truncated_case_count} additional '
            "indexed cases are omitted by reporting configuration.</p>"
            if cell.truncated_case_count
            else ""
        )
        body = (
            f"{truncation}"
            '<div class="table-wrap case-table"><table>'
            "<thead><tr><th>Sample</th><th>Dataset</th><th>Family</th>"
            "<th>Difficulty</th><th>Case</th>"
            "<th>Expected</th><th>Prediction</th><th>Inference valid</th>"
            "<th>Evaluation valid</th><th>Latency ms</th><th>Error</th>"
            "<th>Evidence</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )

    return (
        '<details class="model-details">'
        f"<summary>{escape(cell.model_key)} · n={cell.sample_count} · "
        f"failures={cell.failure_count}</summary>{body}</details>"
    )
