from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from benchmark_core import to_jsonable

from model_capability_bench.reporting.config import ReportingConfig
from model_capability_bench.reporting.html import render_html_report
from model_capability_bench.reporting.model import BenchmarkReport


@dataclass(frozen=True)
class ReportOutputs:
    html_path: Path
    json_path: Path


def write_report(
    report: BenchmarkReport,
    config: ReportingConfig,
    output_dir: Path,
    *,
    html_path: Path | None = None,
    json_path: Path | None = None,
) -> ReportOutputs:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_html = html_path or output_dir / config.html_filename
    resolved_json = json_path or output_dir / config.json_filename
    resolved_html.parent.mkdir(parents=True, exist_ok=True)
    resolved_json.parent.mkdir(parents=True, exist_ok=True)

    resolved_json.write_text(
        json.dumps(
            to_jsonable(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    resolved_html.write_text(
        render_html_report(report, config),
        encoding="utf-8",
    )
    return ReportOutputs(
        html_path=resolved_html,
        json_path=resolved_json,
    )
