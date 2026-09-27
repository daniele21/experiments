from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

T = TypeVar("T")
ArmStatus = Literal["success", "error"]


@dataclass(frozen=True)
class BenchmarkArm:
    model_key: str
    task_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_key.strip():
            raise ValueError("model_key must not be empty")
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")

    @property
    def arm_id(self) -> str:
        return f"{self.model_key}::{self.task_id}"


@dataclass(frozen=True)
class ArmExecution(Generic[T]):
    arm: BenchmarkArm
    status: ArmStatus
    elapsed_s: float
    value: T | None = None
    error_type: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


def execute_arm(
    arm: BenchmarkArm,
    operation: Callable[[], T],
) -> ArmExecution[T]:
    started = time.perf_counter()
    try:
        value = operation()
    except Exception as exc:  # noqa: BLE001 - arm boundary captures execution evidence
        return ArmExecution(
            arm=arm,
            status="error",
            elapsed_s=time.perf_counter() - started,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    return ArmExecution(
        arm=arm,
        status="success",
        elapsed_s=time.perf_counter() - started,
        value=value,
    )
