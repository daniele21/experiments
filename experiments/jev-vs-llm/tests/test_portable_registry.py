from __future__ import annotations

from pathlib import Path

from benchmark_core import load_registry
from benchmark_core.config import load_yaml_mapping

ROOT = Path(__file__).resolve().parents[1]


def test_portable_model_registry_contains_all_local_defaults() -> None:
    registry = load_registry(ROOT / "models.yaml")
    config = load_yaml_mapping(ROOT / "experiments_config.yaml", required=True)
    defaults = list(config["default_models"])

    assert defaults
    assert set(defaults).issubset(registry.models)
    assert all(
        registry.resolve(model_key).runtime.runtime_key == "korgis-local"
        for model_key in defaults
    )


def test_jev_operational_yaml_contains_no_machine_specific_paths() -> None:
    operational = [
        ROOT / "models.yaml",
        ROOT / "datasets.yaml",
        ROOT / "experiments_config.yaml",
    ]

    for path in operational:
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "C:\\" not in text

    assert not (ROOT / "benchmark-models.yaml").exists()


def test_local_model_artifacts_are_resolved_externally() -> None:
    registry = load_registry(ROOT / "models.yaml")

    for model in registry.models.values():
        assert model.runtime_key == "korgis-local"
        assert model.artifact is not None
        assert model.artifact.metadata["resolved_by"] == "external-korgis-registry"
        assert model.artifact.source is None
