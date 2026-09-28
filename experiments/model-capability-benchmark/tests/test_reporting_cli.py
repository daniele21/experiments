from __future__ import annotations

import json
import sys
from pathlib import Path

from model_capability_bench.cli import main


def test_report_cli_requires_no_provider_environment(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_dir = tmp_path / "persisted-run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "run": {
                    "run_id": "historical-run",
                    "run_group": "historical-group",
                },
                "suite": {
                    "suite_id": "capability-core",
                    "version": "1",
                    "profile": "smoke",
                    "seed": 42,
                },
                "models": [],
                "capabilities": [],
                "config_checksums": {},
                "evidence": {},
            }
        ),
        encoding="utf-8",
    )

    for name in (
        "OPENAI_API_KEY",
        "KORGIS_BASE_URL",
        "MINICPM_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    html_path = tmp_path / "custom.html"
    json_path = tmp_path / "custom.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "model-bench",
            "report",
            "--run-dir",
            str(run_dir),
            "--html",
            str(html_path),
            "--json",
            str(json_path),
        ],
    )

    assert main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["run_id"] == "historical-run"
    assert Path(output["html_path"]) == html_path
    assert Path(output["json_path"]) == json_path
    assert html_path.is_file()
    assert json_path.is_file()
