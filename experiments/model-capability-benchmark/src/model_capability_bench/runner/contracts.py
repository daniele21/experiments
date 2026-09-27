from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from benchmark_core import InferenceProvider, ResolvedModel


@runtime_checkable
class ModelRuntime(Protocol):
    def prepare(self, model: ResolvedModel) -> InferenceProvider:
        """Make the selected model ready and return its inference provider."""

    def release(self, model: ResolvedModel) -> None:
        """Release model-specific runtime resources."""


RuntimeResolver = Callable[[ResolvedModel], ModelRuntime]


@dataclass(frozen=True)
class RunnerConfig:
    run_group: str
    profile: str
    model_keys: tuple[str, ...]
    capability_ids: tuple[str, ...] | None = None
    seed: int = 42
    resume: bool = True
    retry_failures: bool = False
    run_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_group.strip():
            raise ValueError("run_group must not be empty")
        if not self.profile.strip():
            raise ValueError("profile must not be empty")
        if not self.model_keys:
            raise ValueError("model_keys must not be empty")
        if any(not key.strip() for key in self.model_keys):
            raise ValueError("model_keys must not contain empty values")
        if self.capability_ids is not None and any(
            not capability_id.strip() for capability_id in self.capability_ids
        ):
            raise ValueError("capability_ids must not contain empty values")


@dataclass(frozen=True)
class RunnerSummary:
    run_id: str
    run_group: str
    planned_cases: int
    completed_cases: int
    failed_cases: int
    skipped_cases: int
    model_failures: int
    aggregate_count: int
    output_dir: str
    metadata: Mapping[str, object] = field(default_factory=dict)


def deduplicate(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
