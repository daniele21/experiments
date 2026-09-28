from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from benchmark_core.contracts import GenerationConfig
from benchmark_core.reproducibility import fingerprint_values


@dataclass(frozen=True)
class BenchmarkCaseIdentity:
    suite_id: str
    suite_version: str
    model_key: str
    model_id: str
    runtime_key: str
    capability_id: str
    task_id: str
    task_version: str
    dataset_id: str
    dataset_revision: str
    dataset_split: str
    selection_fingerprint: str
    sample_id: str
    profile: str
    generation: GenerationConfig
    prompt_id: str | None = None
    prompt_version: str | None = None
    metadata: Mapping[str, Any] | None = None

    @property
    def case_id(self) -> str:
        return fingerprint_values(
            [
                self.suite_id,
                self.suite_version,
                self.model_key,
                self.model_id,
                self.runtime_key,
                self.capability_id,
                self.task_id,
                self.task_version,
                self.prompt_id,
                self.prompt_version,
                self.dataset_id,
                self.dataset_revision,
                self.dataset_split,
                self.selection_fingerprint,
                self.sample_id,
                self.profile,
                self.generation.temperature,
                self.generation.max_output_tokens,
                self.generation.seed,
                list(self.generation.stop),
                dict(self.generation.extra),
                dict(self.metadata or {}),
            ]
        )
