from __future__ import annotations

from pathlib import Path

from benchmark_core.config import parse_csv_selection
from scripts.run_local_matrix import load_config, load_registry_models


def test_local_runner_config_wrappers_use_shared_yaml_loader(tmp_path: Path) -> None:
    config = tmp_path / "experiments.yaml"
    registry = tmp_path / "models.yaml"

    config.write_text(
        """
dataset: public
default_models:
  - model-a
""".strip(),
        encoding="utf-8",
    )
    registry.write_text(
        """
models:
  model-a:
    model_id: vendor/model-a
    quantization: Q4_K_M
""".strip(),
        encoding="utf-8",
    )

    assert load_config(config) == {
        "dataset": "public",
        "default_models": ["model-a"],
    }
    assert load_registry_models(registry) == {
        "model-a": {
            "model_id": "vendor/model-a",
            "quantization": "Q4_K_M",
        }
    }


def test_shared_selection_matches_local_matrix_semantics() -> None:
    available = ["model-a", "model-b"]

    assert parse_csv_selection("all", available=available) == available
    assert parse_csv_selection("model-b,model-a,model-b") == ["model-b", "model-a"]
