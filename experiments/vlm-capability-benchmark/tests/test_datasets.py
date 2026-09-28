from __future__ import annotations

from pathlib import Path

from vlm_bench.datasets import load_dataset_cases


def test_controlled_ui_dataset_has_unique_valid_assets() -> None:
    dataset = Path(__file__).parents[1] / "datasets" / "controlled_ui_grounding.yaml"

    cases = load_dataset_cases(dataset)

    assert [case.sample_id for case in cases] == [
        "ui-create-project-001",
        "ui-settings-001",
    ]
    assert all(case.asset_path.is_file() for case in cases)
    assert all(case.target_box is not None for case in cases)
