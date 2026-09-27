from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from benchmark_core.contracts import InferenceError

TransportErrorKind = Literal[
    "authentication",
    "timeout",
    "transport",
    "invalid_response",
]


@dataclass
class TransportError(RuntimeError):
    kind: TransportErrorKind
    message: str
    retryable: bool = False
    status_code: int | None = None
    detail: str | None = None

    def __str__(self) -> str:
        return self.message


def inference_error_from_exception(exc: Exception) -> InferenceError:
    if isinstance(exc, TransportError):
        details = {}
        if exc.status_code is not None:
            details["status_code"] = exc.status_code
        if exc.detail is not None:
            details["detail"] = exc.detail
        return InferenceError(
            kind=exc.kind,
            message=exc.message,
            retryable=exc.retryable,
            details=details,
        )
    if isinstance(exc, TimeoutError):
        return InferenceError(
            kind="timeout",
            message=str(exc),
            retryable=True,
        )
    return InferenceError(
        kind="unknown",
        message=f"{type(exc).__name__}: {exc}",
        retryable=False,
    )
