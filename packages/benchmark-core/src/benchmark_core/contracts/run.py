from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from benchmark_core.contracts.inference import GenerationConfig
from benchmark_core.contracts.registry import ModelSpec, ProviderSpec, RuntimeSpec


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_group: str
    suite_id: str
    seed: int
    profile: str
    started_at_utc: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("run_group", self.run_group),
            ("suite_id", self.suite_id),
            ("profile", self.profile),
            ("started_at_utc", self.started_at_utc),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class RunManifest:
    schema_version: str
    context: RunContext
    benchmark_core_version: str
    model: ModelSpec
    runtime: RuntimeSpec
    provider: ProviderSpec
    task_id: str
    task_version: str
    generation: GenerationConfig
    git_commit: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    dataset_id: str | None = None
    dataset_revision: str | None = None
    dataset_split: str | None = None
    sample_selection_fingerprint: str | None = None
    pricing: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("schema_version", self.schema_version),
            ("benchmark_core_version", self.benchmark_core_version),
            ("task_id", self.task_id),
            ("task_version", self.task_version),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
