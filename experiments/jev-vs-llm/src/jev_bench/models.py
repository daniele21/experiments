from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

QuestionType = Literal["choice", "score", "noul"]


@dataclass(frozen=True)
class QuestionSpec:
    id: str
    type: QuestionType
    instructions: str
    criteria: dict[str, str] | list[str] | None = None


@dataclass
class Decision:
    question_id: str
    value: str | float
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None


@dataclass
class ProviderResult:
    provider: str
    model: str
    answers: dict[str, Decision]
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    valid: bool = True
    error: str | None = None
    raw: Any = None


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    state: Any
    expected: dict[str, str | float]
    metadata: dict[str, Any] = field(default_factory=dict)
