from __future__ import annotations

from typing import Protocol, runtime_checkable

from benchmark_core.contracts import InferenceRequest, InferenceResult


@runtime_checkable
class InferenceProvider(Protocol):
    provider_id: str

    def generate(self, request: InferenceRequest) -> InferenceResult:
        """Run one provider inference without task-specific evaluation."""
