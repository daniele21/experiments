from __future__ import annotations

import sys
import time
from typing import Callable, Protocol, TextIO


class ProgressReporter(Protocol):
    def run_started(
        self,
        *,
        run_id: str,
        dataset: str,
        cases: int,
        models: list[str],
        output: str,
    ) -> None: ...

    def model_started(self, *, model: str, index: int, total: int) -> None: ...

    def warmups_started(self, *, model: str, total: int) -> None: ...

    def warmup_completed(self, *, model: str, completed: int, total: int) -> None: ...

    def cases_started(self, *, model: str, total: int) -> None: ...

    def case_completed(
        self,
        *,
        model: str,
        completed: int,
        total: int,
        case_id: str,
        latency_ms: float,
        errors: int,
    ) -> None: ...

    def model_completed(
        self,
        *,
        model: str,
        completed: int,
        total: int,
        errors: int,
    ) -> None: ...

    def run_completed(self) -> None: ...


class NullProgress:
    def run_started(self, **_: object) -> None:
        pass

    def model_started(self, **_: object) -> None:
        pass

    def warmups_started(self, **_: object) -> None:
        pass

    def warmup_completed(self, **_: object) -> None:
        pass

    def cases_started(self, **_: object) -> None:
        pass

    def case_completed(self, **_: object) -> None:
        pass

    def model_completed(self, **_: object) -> None:
        pass

    def run_completed(self) -> None:
        pass


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_latency(latency_ms: float) -> str:
    if latency_ms >= 1000:
        return f"{latency_ms / 1000:.1f}s"
    return f"{latency_ms:.0f}ms"


def _bar(completed: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "░" * width
    filled = min(width, max(0, round(width * completed / total)))
    return "█" * filled + "░" * (width - filled)


class TerminalProgress:
    """TTY-friendly benchmark progress while keeping stdout machine-readable."""

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        interactive: bool | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.stream = stream or sys.stderr
        detected = bool(getattr(self.stream, "isatty", lambda: False)())
        self.interactive = detected if interactive is None else interactive
        self.clock = clock
        self._live_active = False
        self._model_started_at: float | None = None
        self._cases_started_at: float | None = None
        self._model_index = 0
        self._model_total = 0

    def _clear_live(self) -> None:
        if self.interactive and self._live_active:
            self.stream.write("\r\033[2K")
            self._live_active = False

    def _line(self, message: str) -> None:
        self._clear_live()
        self.stream.write(message + "\n")
        self.stream.flush()

    def _live(self, message: str) -> None:
        if not self.interactive:
            return
        self.stream.write("\r\033[2K" + message)
        self.stream.flush()
        self._live_active = True

    def run_started(
        self,
        *,
        run_id: str,
        dataset: str,
        cases: int,
        models: list[str],
        output: str,
    ) -> None:
        self._line(f"Run: {run_id}")
        self._line(f"Dataset: {dataset} — {cases} cases")
        self._line(f"Models: {len(models)}")
        self._line(f"Results: {output}")
        self._line("")

    def model_started(self, *, model: str, index: int, total: int) -> None:
        self._model_index = index
        self._model_total = total
        self._model_started_at = self.clock()
        self._cases_started_at = None
        if self.interactive:
            self._live(f"[{index}/{total} {model}] Activating…")
        else:
            self._line(f"→ [{index}/{total}] {model}")

    def warmups_started(self, *, model: str, total: int) -> None:
        if total > 0:
            self._live(
                f"[{self._model_index}/{self._model_total} {model}] "
                f"Warmup 0/{total}"
            )

    def warmup_completed(self, *, model: str, completed: int, total: int) -> None:
        suffix = " ✓" if completed >= total else ""
        message = (
            f"[{self._model_index}/{self._model_total} {model}] "
            f"Warmup {completed}/{total}{suffix}"
        )
        if self.interactive:
            self._live(message)
        elif completed >= total:
            self._line(f"  Warmup {completed}/{total} ✓")

    def cases_started(self, *, model: str, total: int) -> None:
        self._cases_started_at = self.clock()
        self._live(
            f"[{self._model_index}/{self._model_total} {model}] "
            f"Cases 0/{total} [{_bar(0, total)}] 0% | Errors: 0"
        )

    def case_completed(
        self,
        *,
        model: str,
        completed: int,
        total: int,
        case_id: str,
        latency_ms: float,
        errors: int,
    ) -> None:
        if not self.interactive:
            return
        now = self.clock()
        started = self._cases_started_at if self._cases_started_at is not None else now
        elapsed = max(0.0, now - started)
        eta = (elapsed / completed) * (total - completed) if completed else 0.0
        percent = round((completed / total) * 100) if total else 100
        self._live(
            f"[{self._model_index}/{self._model_total} {model}] "
            f"Cases {completed}/{total} [{_bar(completed, total)}] {percent}%"
            f" | Last: {case_id}"
            f" | Latency: {_format_latency(latency_ms)}"
            f" | Elapsed: {_format_duration(elapsed)}"
            f" | ETA: {_format_duration(eta)}"
            f" | Errors: {errors}"
        )

    def model_completed(
        self,
        *,
        model: str,
        completed: int,
        total: int,
        errors: int,
    ) -> None:
        now = self.clock()
        started = self._model_started_at if self._model_started_at is not None else now
        elapsed = max(0.0, now - started)
        self._line(
            f"✓ {model} {completed}/{total} | Errors: {errors} "
            f"| Elapsed: {_format_duration(elapsed)}"
        )

    def run_completed(self) -> None:
        self._line("✓ Run complete")
