from __future__ import annotations

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.html_format import escape
from model_capability_bench.reporting.html_sections import (
    render_capability_sections,
    render_events,
    render_model_table,
    render_primary_matrix,
)
from model_capability_bench.reporting.html_style import REPORT_CSS
from model_capability_bench.reporting.model import BenchmarkReport


def render_html_report(
    report: BenchmarkReport,
    config: ReportingConfig,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(report.title)}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<main>
<header>
  <h1>{escape(report.title)}</h1>
  <div class="meta">
    <span><strong>Run:</strong> {escape(report.run_id)}</span>
    <span><strong>Group:</strong> {escape(report.run_group)}</span>
    <span><strong>Suite:</strong> {escape(report.suite_id)} v{escape(report.suite_version)}</span>
    <span><strong>Profile:</strong> {escape(report.profile)}</span>
    <span><strong>Generated:</strong> {escape(report.generated_at_utc)}</span>
  </div>
  <div class="note">{escape(report.cost_semantics)}</div>
</header>
{render_model_table(report)}
{render_primary_matrix(report, config)}
{render_capability_sections(report, config)}
{render_events(report)}
</main>
</body>
</html>
"""
