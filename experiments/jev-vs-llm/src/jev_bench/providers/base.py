from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from jev_bench.models import ProviderResult, QuestionSpec


class DecisionProvider(ABC):
    name: str

    @abstractmethod
    def evaluate(self, state: Any, questions: Sequence[QuestionSpec]) -> ProviderResult:
        """Evaluate independent typed questions against one shared state."""
