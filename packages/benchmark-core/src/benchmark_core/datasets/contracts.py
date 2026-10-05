from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from benchmark_core.contracts import Sample

CacheMode = Literal["none", "download", "repository", "external"]


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    version: str
    adapter_id: str
    source: str
    revision: str
    split: str
    license_id: str | None = None
    sample_schema_version: str = "1"
    cache_mode: CacheMode = "none"
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("dataset_id", self.dataset_id),
            ("version", self.version),
            ("adapter_id", self.adapter_id),
            ("source", self.source),
            ("revision", self.revision),
            ("split", self.split),
            ("sample_schema_version", self.sample_schema_version),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.cache_mode not in {"none", "download", "repository", "external"}:
            raise ValueError(f"Unsupported cache_mode: {self.cache_mode}")


@dataclass(frozen=True)
class DatasetProfileSpec:
    profile_id: str
    default_max_cases: int | None
    dataset_max_cases: Mapping[str, int | None] = field(default_factory=dict)
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be empty")
        if self.default_max_cases is not None and self.default_max_cases <= 0:
            raise ValueError("default_max_cases must be > 0 or null")
        for dataset_id, value in self.dataset_max_cases.items():
            if not str(dataset_id).strip():
                raise ValueError("dataset_max_cases keys must not be empty")
            if value is not None and value <= 0:
                raise ValueError(
                    f"dataset_max_cases[{dataset_id!r}] must be > 0 or null"
                )

    def max_cases_for(self, dataset_id: str) -> int | None:
        return self.dataset_max_cases.get(dataset_id, self.default_max_cases)


@dataclass(frozen=True)
class DatasetLoadContext:
    cache_dir: Path
    profile: DatasetProfileSpec
    seed: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    max_cases_override: int | None = None
    selection: Mapping[str, Any] = field(default_factory=dict)
    max_cases_override_enabled: bool = False

    def __post_init__(self) -> None:
        if self.max_cases_override is not None and self.max_cases_override <= 0:
            raise ValueError("max_cases_override must be > 0 or null")

    def max_cases_for(self, dataset_id: str) -> int | None:
        if self.max_cases_override_enabled or self.max_cases_override is not None:
            return self.max_cases_override
        return self.profile.max_cases_for(dataset_id)


@dataclass(frozen=True)
class DatasetLoadResult:
    spec: DatasetSpec
    samples: tuple[Sample, ...]
    selection_fingerprint: str
    available_count: int
    source_checksums: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.available_count < 0:
            raise ValueError("available_count must be >= 0")
        if len(self.samples) > self.available_count:
            raise ValueError("selected samples cannot exceed available_count")
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("dataset result contains duplicate sample IDs")
        if not self.selection_fingerprint.startswith("sha256:"):
            raise ValueError("selection_fingerprint must be a sha256 fingerprint")


@runtime_checkable
class BenchmarkDataset(Protocol):
    @property
    def spec(self) -> DatasetSpec:
        """Static, versioned dataset definition."""

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        """Load, normalize and deterministically select benchmark samples."""
