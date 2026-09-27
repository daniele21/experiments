from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import (
    BenchmarkDataset,
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetPluginRegistry,
    DatasetProfileSpec,
    DatasetRegistry,
    DatasetRegistryError,
    DatasetSpec,
    Sample,
    fingerprint_values,
    load_dataset_profiles,
    load_dataset_specs,
    sha256_file,
)


class _FixtureDataset:
    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> DatasetSpec:
        return self._spec

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        available = (
            Sample(sample_id="a", input="A", expected="x"),
            Sample(sample_id="b", input="B", expected="y"),
        )
        max_cases = context.profile.max_cases_for(self.spec.dataset_id)
        samples = available if max_cases is None else available[:max_cases]
        return DatasetLoadResult(
            spec=self.spec,
            samples=samples,
            selection_fingerprint=fingerprint_values(
                [sample.sample_id for sample in samples]
            ),
            available_count=len(available),
        )


def _dataset_spec() -> DatasetSpec:
    return DatasetSpec(
        dataset_id="fixture",
        version="1",
        adapter_id="fixture-adapter",
        source="repository",
        revision="v1",
        split="test",
        license_id="fixture",
        cache_mode="none",
    )


def test_dataset_plugin_registry_builds_structural_adapter(tmp_path: Path) -> None:
    plugins = DatasetPluginRegistry()
    plugins.register("fixture-adapter", _FixtureDataset)
    registry = DatasetRegistry.from_specs({"fixture": _dataset_spec()}, plugins)

    dataset = registry.get("fixture")
    assert isinstance(dataset, BenchmarkDataset)
    assert registry.summary() == {
        "datasets": 1,
        "dataset_ids": ["fixture"],
        "adapters": ["fixture-adapter"],
    }

    context = DatasetLoadContext(
        cache_dir=tmp_path,
        profile=DatasetProfileSpec("smoke", default_max_cases=1),
        seed=42,
    )
    loaded = registry.load("fixture", context)
    assert [sample.sample_id for sample in loaded.samples] == ["a"]
    assert loaded.available_count == 2


def test_dataset_profile_supports_declarative_overrides() -> None:
    profile = DatasetProfileSpec(
        profile_id="budget",
        default_max_cases=100,
        dataset_max_cases={
            "banking77": 154,
            "controlled": None,
        },
    )

    assert profile.max_cases_for("other") == 100
    assert profile.max_cases_for("banking77") == 154
    assert profile.max_cases_for("controlled") is None


def test_dataset_load_result_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DatasetLoadResult(
            spec=_dataset_spec(),
            samples=(
                Sample(sample_id="same", input="A"),
                Sample(sample_id="same", input="B"),
            ),
            selection_fingerprint=fingerprint_values(["same", "same"]),
            available_count=2,
        )


def test_dataset_catalog_and_profiles_are_strict(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets.yaml"
    datasets.write_text(
        """
datasets:
  fixture:
    version: "1"
    adapter: fixture-adapter
    source: repository
    revision: v1
    split: test
    cache_mode: repository
    sample_schema_version: "2"
""".strip(),
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        """
profiles:
  smoke:
    max_cases: 20
    datasets:
      fixture: 2
  full:
    max_cases: null
""".strip(),
        encoding="utf-8",
    )

    spec = load_dataset_specs(datasets)["fixture"]
    loaded_profiles = load_dataset_profiles(profiles)

    assert spec.sample_schema_version == "2"
    assert spec.cache_mode == "repository"
    assert loaded_profiles["smoke"].max_cases_for("fixture") == 2
    assert loaded_profiles["full"].max_cases_for("fixture") is None

    datasets.write_text(
        """
datasets:
  fixture:
    version: "1"
    adapter: fixture-adapter
    source: repository
    revision: v1
    split: test
    cache_mode: repository
    reviison: typo
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(DatasetRegistryError, match="reviison"):
        load_dataset_specs(datasets)


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "fixture.txt"
    path.write_bytes(b"benchmark-data")

    assert sha256_file(path) == (
        "8c3cb8033cc033a205a6a5eee499f12d"
        "dbed1515feb56171435c10537131d0ae"
    )
