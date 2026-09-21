"""report.py.

Modular entry point for building the interactive Decision Benchmark Explorer dashboard.
Delegates data transformation and metrics calculation to `jev_bench.reporting`
and renders a self-contained, responsive React application.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jev_bench.reporting.data import (
    compute_overview as _overview,
    select_run_group as _select_run_group,
    with_series as _with_series,
)
from jev_bench.reporting.export import build_benchmark_payload

logger = logging.getLogger(__name__)

# Root directory of the React dashboard project
_DASHBOARD_DIR = Path(__file__).parent.parent.parent / "dashboard"
_TEMPLATE_DIST = _DASHBOARD_DIR / "dist" / "index.html"


def _inject_payload_into_html(template_html: str, payload: dict[str, Any]) -> str:
    """Inject window.__BENCHMARK_DATA__ script tag into HTML template."""
    json_str = json.dumps(payload, ensure_ascii=False)
    injection = f'<script id="benchmark-data">window.__BENCHMARK_DATA__ = {json_str};</script>'

    # If already has injection, replace it
    if '<script id="benchmark-data">' in template_html:
        return re.sub(
            r'<script id="benchmark-data">.*?</script>',
            injection,
            template_html,
            flags=re.DOTALL,
        )

    # Insert before </head>
    if "</head>" in template_html:
        return template_html.replace("</head>", f"  {injection}\n</head>", 1)

    return f"{injection}\n{template_html}"


def build_report(
    raw_csv: Path,
    output_html: Path,
    run_group: str | None = "latest_per_model",
) -> None:
    """Generate the interactive decision benchmark dashboard from raw results CSV.

    1. Extracts, aggregates, and validates benchmark metrics across all evaluated models.
    2. Writes structured JSON payload for both API consumers and the React dashboard.
    3. Bundles or updates the standalone React single-file report at `output_html`.
    """
    raw_csv = Path(raw_csv)
    output_html = Path(output_html)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    # 1. Build complete structured payload
    payload = build_benchmark_payload(raw_csv, run_group)

    # 2. Persist JSON data in results/ and dashboard/src/data/
    json_out = output_html.parent / "benchmark_data.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    dashboard_data_path = _DASHBOARD_DIR / "src" / "data" / "benchmark_data.json"
    if dashboard_data_path.parent.exists():
        with open(dashboard_data_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    # 3. If dist template exists, we can immediately write to output_html with injected data
    if _TEMPLATE_DIST.exists():
        template_html = _TEMPLATE_DIST.read_text(encoding="utf-8")
        rendered = _inject_payload_into_html(template_html, payload)
        output_html.write_text(rendered, encoding="utf-8")

    # 4. If npm is available, trigger a fresh rebuild of the singlefile bundle
    npm_bin = shutil.which("npm")
    if npm_bin and _DASHBOARD_DIR.exists() and (_DASHBOARD_DIR / "package.json").exists():
        try:
            subprocess.run(
                [npm_bin, "run", "build"],
                cwd=str(_DASHBOARD_DIR),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if _TEMPLATE_DIST.exists():
                template_html = _TEMPLATE_DIST.read_text(encoding="utf-8")
                rendered = _inject_payload_into_html(template_html, payload)
                output_html.write_text(rendered, encoding="utf-8")
        except Exception as exc:
            logger.warning("Vite dashboard build returned: %s. Falling back to injected template.", exc)

    if not output_html.exists():
        raise FileNotFoundError(
            f"Dashboard could not be written to {output_html} and template was not found at {_TEMPLATE_DIST}."
        )

    logger.info("Decision benchmark dashboard updated at: %s", output_html)


__all__ = ["build_report", "_select_run_group", "_with_series", "_overview"]
