from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    pii_type: str
    value: str

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Case:
    case_id: str
    profile: str
    text: str
    gold: tuple[Span, ...]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finding:
    pii_type: str
    value: str
    start: int
    end: int
    field_name: str = ""
    field_description: str = ""


@dataclass
class InferenceResult:
    case_id: str
    model: str
    valid: bool
    latency_ms: float
    findings: list[Finding]
    raw_content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data
