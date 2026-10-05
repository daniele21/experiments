from __future__ import annotations

import math
import shutil
import sys
from collections.abc import Callable
from threading import Event, RLock, Thread
from time import monotonic
from typing import Self, TextIO

from model_capability_bench.observability import BenchmarkEvent


def _duration(seconds: float) -> str:
    seconds = max(0, math.ceil(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class TerminalProgress:
    """Render persisted lifecycle events on stderr, leaving stdout as JSON.

    Counts and ETA refer to the current model/capability. Only cases executed in
    this invocation contribute to ETA; resumed cases advance the counter only.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: TextIO | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.enabled = enabled
        self.stream = sys.stderr if stream is None else stream
        self.clock = clock
        self.tty = self.stream.isatty()
        self.interval = 1.0 if self.tty else 10.0
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self.started = clock()
        self._last_render = float("-inf")
        self.stage = "preflight"
        self.model = ""
        self.capability = ""
        self.sample = ""
        self.total: int | None = None
        self.completed = 0
        self.failed = 0
        self.skipped = 0
        self.case_started: float | None = None
        self.case_seconds = 0.0
        self.measured_cases = 0
        self.had_failure = False
        self._rendered_rows = 0

    def __enter__(self) -> Self:
        self.started = self.clock()
        if self.enabled:
            self.render(force=True)
            self._thread = Thread(target=self._tick, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        if exc_type is not None:
            self.phase("INTERRUPTED" if issubclass(exc_type, KeyboardInterrupt) else "FAILED")
        else:
            self.phase("PARTIAL" if self.had_failure else "COMPLETED")
        if self.enabled and self.tty:
            self.stream.write("\n")
            self.stream.flush()

    def _tick(self) -> None:
        while not self._stop.wait(0.25):
            self.render()

    def phase(self, stage: str) -> None:
        with self._lock:
            self.stage = stage
            self.sample = ""
            self.render(force=True)

    def on_event(self, event: BenchmarkEvent) -> None:
        if not self.enabled:
            return
        with self._lock:
            kind = event.event_type
            now = self.clock()
            if event.model_key:
                self.model = event.model_key
            if event.capability_id:
                self.capability = event.capability_id
            if event.sample_id:
                self.sample = event.sample_id
            if event.error_type or kind.endswith(".failed"):
                self.had_failure = True
            phases = {
                "model.prepare.started": "preparing model",
                "capability.loading.started": "loading datasets",
                "case.started": "building request",
                "inference.started": "inference",
                "evaluation.started": "evaluation",
                "capability.completed": "capability complete",
                "model.release.started": "releasing model",
                "capability.aggregated": "aggregating",
                "run.completed": "saving results",
            }
            if kind in phases:
                self.stage = phases[kind]
            if kind in {"model.prepare.started", "capability.loading.started"}:
                self.total = None
                self.completed = self.failed = self.skipped = 0
                self.sample = ""
                self.case_started = None
                if kind == "model.prepare.started":
                    self.capability = ""
            if kind == "capability.started":
                self.total = int(event.metadata["planned_cases"])
                self.completed = self.failed = self.skipped = 0
                self.case_seconds = 0.0
                self.measured_cases = 0
                self.case_started = None
                self.sample = ""
                self.stage = "running"
            elif kind == "case.started":
                self.case_started = now
            elif kind in {"case.completed", "case.failed"}:
                if self.case_started is not None:
                    self.case_seconds += now - self.case_started
                    self.measured_cases += 1
                self.case_started = None
                if kind == "case.completed":
                    self.completed += 1
                else:
                    self.failed += 1
                self.stage = "running" if kind == "case.completed" else "case failed"
            elif kind == "case.skipped":
                self.skipped += 1
                if event.metadata.get("previous_status") == "failed":
                    self.had_failure = True
                self.stage = "resuming"
            force = kind in {
                "model.prepare.started", "capability.loading.started",
                "capability.started", "capability.completed", "run.completed",
            } or kind.endswith(".failed")
            self.render(force=force)

    def line(self) -> str:
        with self._lock:
            now = self.clock()
            done = self.completed + self.failed + self.skipped
            progress = "cases --"
            eta = "-- (collecting samples)"
            if self.total is not None:
                ratio = done / self.total if self.total else 1.0
                filled = min(16, int(ratio * 16))
                bar = "#" * filled + "-" * (16 - filled)
                progress = f"[{bar}] {done}/{self.total} {ratio:.0%}"
                remaining = max(0, self.total - done)
                if remaining == 0:
                    eta = "00:00:00"
                elif self.measured_cases:
                    estimate = self.case_seconds / self.measured_cases * remaining
                    if self.case_started is not None:
                        estimate -= now - self.case_started
                    eta = f"~{_duration(estimate)}" if estimate > 0 else "over estimate"
            if self.total is None:
                eta = "--"
            context = " / ".join(part for part in (self.model, self.capability) if part)
            sample = f" | case {self.sample}" if self.sample else ""
            return (
                f"{context + ' | ' if context else ''}{self.stage} | {progress}"
                f" | ok {self.completed} failed {self.failed} resumed {self.skipped}"
                f" | elapsed {_duration(now - self.started)} | ETA {eta}{sample}"
            )

    def render(self, *, force: bool = False) -> None:
        if not self.enabled:
            return
        with self._lock:
            now = self.clock()
            if not force and now - self._last_render < self.interval:
                return
            self._last_render = now
            line = self.line()
            if self.tty:
                # Keep rows within the terminal width so refreshes never wrap
                # into an ever-growing trail of progress lines.
                parts = line.split(" | ")
                timing_index = next(
                    index for index, part in enumerate(parts) if part.startswith("elapsed ")
                )
                count_index = next(
                    index for index, part in enumerate(parts)
                    if part.startswith("[") or part == "cases --"
                )
                rows = [
                    " | ".join(parts[:count_index] + parts[timing_index + 2:]),
                    " | ".join(parts[count_index:timing_index]),
                    " | ".join(parts[timing_index:timing_index + 2]),
                ]
                width = max(20, shutil.get_terminal_size().columns - 1)
                prefix = f"\033[{self._rendered_rows - 1}A" if self._rendered_rows else ""
                self.stream.write(prefix + "\n".join(
                    "\r\033[2K" + row[:width] for row in rows
                ))
                self._rendered_rows = len(rows)
            else:
                self.stream.write(line + "\n")
            self.stream.flush()
