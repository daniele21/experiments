import json
from pathlib import Path

import pandas as pd

from jev_bench.decisio_results import decisio_output_frame, publish_decisio_results


def _artifacts(tmp_path: Path) -> tuple[Path, Path]:
    matrix = tmp_path / "run"
    output = matrix / "qwen-test"
    output.mkdir(parents=True)
    (output / "fixture.json").write_text(
        json.dumps(
            {
                "question": {"id": "intent"},
                "cases": [
                    {
                        "case_id": "case-1",
                        "state": "card failed",
                        "metadata": {
                            "dataset_revision": "rev-1",
                            "source_split": "test",
                            "benchmark_tier": "public",
                        },
                    }
                ],
            }
        )
    )
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-09-24T12:00:00Z",
                "dataset": "banking77",
                "config": {"device": "metal"},
            }
        )
    )
    rows = []
    for method, choice in (("semantic", "wrong"), ("json", "card_failed")):
        rows.append(
            {
                "method": method,
                "case_id": "case-1",
                "expected": "card_failed",
                "choice": choice,
                "correct": choice == "card_failed",
                "valid": True,
                "latency_ms": 12.5,
                "runtime": {
                    "physically_evaluated_tokens": 20,
                    "reused_prefix_tokens": 80,
                },
                "result": {
                    "distribution": {choice: 0.75},
                    "generated_tokens": 3 if method == "json" else 0,
                },
                "error": None,
            }
        )
    (output / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return matrix, output


def test_decisio_artifacts_map_to_distinct_dashboard_configurations(tmp_path):
    matrix, output = _artifacts(tmp_path)
    frame = decisio_output_frame(matrix, "qwen-test", output)
    assert set(frame["configuration_id"]) == {"semantic-metal", "json-metal"}
    assert set(frame["inference_device"]) == {"metal"}
    assert set(frame["provider"]) == {"local-decisio"}
    assert set(frame["dataset"]) == {"banking77"}
    assert frame.set_index("configuration_id").loc["semantic-metal", "confidence"] == 0.75
    assert frame.set_index("configuration_id").loc["json-metal", "output_tokens"] == 3


def test_publish_is_idempotent_and_rebuilds_dashboard(tmp_path, monkeypatch):
    matrix, output = _artifacts(tmp_path)
    csv = tmp_path / "results.csv"
    html = tmp_path / "report.html"
    builds = []
    monkeypatch.setattr(
        "jev_bench.decisio_results.build_report",
        lambda *args, **kwargs: builds.append((args, kwargs)),
    )
    for _ in range(2):
        assert publish_decisio_results(
            matrix,
            [("qwen-test", output)],
            output_csv=csv,
            report_html=html,
        ) == 2
    saved = pd.read_csv(csv)
    assert len(saved) == 2
    assert len(builds) == 2
