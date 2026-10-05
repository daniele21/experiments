from __future__ import annotations

from io import StringIO

import pytest

from model_capability_bench.observability import build_event
from model_capability_bench.runner.progress import TerminalProgress


def _event(progress, kind, **metadata):
    progress.on_event(build_event(
        kind,
        run_id="test",
        model_key="model",
        capability_id="qa-abstention",
        sample_id=metadata.pop("sample_id", None),
        metadata=metadata,
    ))


def test_eta_uses_executed_cases_and_excludes_resume_time():
    now = [0.0]
    progress = TerminalProgress(stream=StringIO(), clock=lambda: now[0])
    _event(progress, "capability.started", planned_cases=5)
    now[0] = 100
    _event(progress, "case.skipped")
    _event(progress, "case.skipped")
    assert "2/5 40%" in progress.line()
    assert "collecting samples" in progress.line()

    _event(progress, "case.started", sample_id="qa-1")
    now[0] = 110
    _event(progress, "case.completed")
    assert "3/5 60%" in progress.line()
    assert "ETA ~00:00:20" in progress.line()
    _event(progress, "case.started")
    _event(progress, "inference.started")
    now[0] = 114
    assert "inference" in progress.line()
    assert "elapsed 00:01:54" in progress.line()
    assert "ETA ~00:00:16" in progress.line()
    now[0] = 120
    _event(progress, "case.failed")
    assert "4/5 80%" in progress.line()
    assert "ok 1 failed 1 resumed 2" in progress.line()
    assert "ETA ~00:00:10" in progress.line()
    _event(progress, "case.skipped")
    assert "5/5 100%" in progress.line()
    assert "ETA 00:00:00" in progress.line()


def test_capability_switch_resets_eta_and_counts():
    progress = TerminalProgress(stream=StringIO())
    _event(progress, "capability.started", planned_cases=12)
    _event(progress, "case.skipped")
    _event(progress, "capability.loading.started")
    assert "cases --" in progress.line()
    _event(progress, "capability.started", planned_cases=40)
    assert "0/40 0%" in progress.line()
    assert "collecting samples" in progress.line()


def test_non_tty_updates_without_ansi_and_ends_partial():
    stream = StringIO()
    now = [0.0]
    with TerminalProgress(stream=stream, clock=lambda: now[0]) as progress:
        _event(progress, "capability.started", planned_cases=1)
        _event(progress, "case.started")
        _event(progress, "inference.started")
        now[0] = 12
        progress.render()
        _event(progress, "case.failed")
    output = stream.getvalue()
    assert "inference" in output
    assert "elapsed 00:00:12" in output
    assert "PARTIAL" in output
    assert "1/1 100%" in output
    assert "\033" not in output
    assert "\r" not in output


@pytest.mark.parametrize("exception, status", [
    (RuntimeError, "FAILED"), (KeyboardInterrupt, "INTERRUPTED"),
])
def test_progress_closes_on_error_or_interrupt(exception, status):
    stream = StringIO()
    with pytest.raises(exception), TerminalProgress(stream=stream):
        raise exception()
    assert status in stream.getvalue()


def test_disabled_progress_is_silent():
    stream = StringIO()
    with TerminalProgress(enabled=False, stream=stream) as progress:
        _event(progress, "capability.started", planned_cases=1)
        _event(progress, "case.failed")
        progress.phase("rendering report")
    assert stream.getvalue() == ""


def test_resuming_terminal_failed_case_keeps_partial_status():
    stream = StringIO()
    with TerminalProgress(stream=stream) as progress:
        _event(progress, "capability.started", planned_cases=1)
        _event(progress, "case.skipped", previous_status="failed")
    assert "resumed 1" in stream.getvalue()
    assert "PARTIAL" in stream.getvalue()


def test_tty_refreshes_multiple_rows_without_wrapping(monkeypatch):
    import os

    class TtyStream(StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(
        "model_capability_bench.runner.progress.shutil.get_terminal_size",
        lambda: os.terminal_size((80, 24)),
    )
    stream = TtyStream()
    with TerminalProgress(stream=stream) as progress:
        _event(progress, "capability.started", planned_cases=60)
        progress.phase("inference")
    output = stream.getvalue()
    assert "\033[2A" in output
    assert "ETA" in output
    for row in output.split("\r\033[2K")[1:]:
        assert len(row.split("\n")[0].split("\033")[0]) <= 79
