from __future__ import annotations

from pathlib import Path

from benchmark_core import (
    DatasetPluginRegistry,
    DatasetRegistry,
    load_dataset_specs,
)

from model_capability_bench.datasets.banking77 import Banking77Dataset
from model_capability_bench.datasets.clinc150 import Clinc150OosDataset
from model_capability_bench.datasets.controlled_yaml import ControlledYamlDataset
from model_capability_bench.datasets.structured_output import (
    StructuredOutputControlledDataset,
)


def build_dataset_plugins() -> DatasetPluginRegistry:
    plugins = DatasetPluginRegistry()
    plugins.register("banking77", Banking77Dataset)
    plugins.register("clinc150-oos", Clinc150OosDataset)
    plugins.register(
        "structured-output-controlled",
        StructuredOutputControlledDataset,
    )
    plugins.register("controlled-yaml", ControlledYamlDataset)
    return plugins


def build_dataset_registry(catalog_path: str | Path) -> DatasetRegistry:
    specs = load_dataset_specs(Path(catalog_path))
    return DatasetRegistry.from_specs(specs, build_dataset_plugins())
