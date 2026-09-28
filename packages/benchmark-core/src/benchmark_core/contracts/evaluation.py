from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

MetricValue = int | float | str | bool | None


@dataclass(frozen=True)
class Sample:
    sample_id: str
    input: Any
    expected: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.sample_id.strip():
            raise ValueError("sample_id must not be empty")


@dataclass(frozen=True)
class MetricResult:
    name: str
    value: MetricValue
    primary: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("metric name must not be empty")


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    sample_id: str
    prediction: Any
    expected: Any
    metrics: tuple[MetricResult, ...] = ()
    valid: bool = True
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.sample_id.strip():
            raise ValueError("sample_id must not be empty")
