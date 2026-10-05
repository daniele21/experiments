from __future__ import annotations

import json
from pathlib import Path

from model_capability_bench.analytics.dashboard_build import (
    inject_dashboard_payloads,
)


def test_dashboard_injection_embeds_projected_payloads_before_runtime(
    tmp_path: Path,
) -> None:
    html = tmp_path / "dashboard.html"
    html.write_text(
        "<html><head><script type=\"module\">window.__BOOT__=true;</script></head>"
        "<body></body></html>",
        encoding="utf-8",
    )
    overview = tmp_path / "overview.json"
    overview.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "models": [],
                "capabilities": ["structured-output"],
                "cells": [],
                "runs": [],
                "label": "</script><unsafe>",
            }
        ),
        encoding="utf-8",
    )
    capability = tmp_path / "capability.json"
    capability.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "capability_id": "structured-output",
                "cells": [],
                "benchmark_signatures": [],
                "family_breakdown": [],
                "disagreements": [],
            }
        ),
        encoding="utf-8",
    )

    inject_dashboard_payloads(
        html_path=html,
        overview_path=overview,
        capability_path=capability,
    )

    rendered = html.read_text(encoding="utf-8")
    assert "window.__MCB_OVERVIEW__=" in rendered
    assert "window.__MCB_CAPABILITY__=" in rendered
    assert "window.__MCB_CAPABILITIES__=" in rendered
    assert '"structured-output"' in rendered
    assert "\\u003c/script>" in rendered
    assert "</script><unsafe>" not in rendered
