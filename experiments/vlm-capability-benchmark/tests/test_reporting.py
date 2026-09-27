from __future__ import annotations

import csv
from pathlib import Path

from vlm_bench.reporting import generate_vlm_report


def test_vlm_report_embeds_input_and_overlays_prediction(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    image = inputs / "fixture.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        '<rect width="100" height="50" fill="white"/>'
        "</svg>",
        encoding="utf-8",
    )
    row = {
        "run_id": "run-1",
        "model_key": "qwen",
        "model_id": "Qwen/Qwen3-VL-4B-Instruct",
        "provider_id": "fake-vlm",
        "task_id": "ui_grounding",
        "sample_id": "ui-1",
        "question": "Where should I click?",
        "input_asset_path": "inputs/fixture.svg",
        "input_asset_sha256": "a" * 64,
        "target_label": "Create project",
        "target_box": "[0.7, 0.1, 0.9, 0.3]",
        "prediction_target": "Create project",
        "prediction_x": "0.8",
        "prediction_y": "0.2",
        "prediction": '{"target":"Create project","x":0.8,"y":0.2}',
        "valid": "True",
        "click_hit": "True",
        "target_match": "True",
        "point_distance": "0.0",
        "latency_ms": "8.4",
        "error_kind": "",
        "error_message": "",
    }
    with (tmp_path / "evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    output = generate_vlm_report(tmp_path, tmp_path / "report.html")

    html = output.read_text(encoding="utf-8")
    assert "data:image/svg+xml;base64," in html
    assert "Create project" in html
    assert "left:80.000%" in html
    assert "left:70.000%" in html
    assert "hit=True" in html
