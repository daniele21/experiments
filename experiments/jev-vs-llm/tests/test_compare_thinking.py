from __future__ import annotations

import importlib.util
import signal
from pathlib import Path
from types import SimpleNamespace


def test_cleanup_includes_worker_sessions_but_excludes_unrelated_processes(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/compare_thinking.py"
    spec = importlib.util.spec_from_file_location("compare_thinking", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Parent 100 owns a separately sessioned backend 101 and its child 102.
    # Other model worker 900 belongs to a completely separate process tree.
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda command, **kw: (
            "100 1 100\n101 100 101\n102 101 101\n900 1 900\n"
            if command[-1] == "pid=,ppid=,pgid="
            else "101 101 S\n900 900 S\n"
        ),
    )
    signals = []
    monkeypatch.setattr(module.os, "killpg", lambda group, sig: signals.append((group, sig)))
    module.stop_owned(SimpleNamespace(pid=100, wait=lambda **kw: 0))
    assert set(signals) == {
        (100, signal.SIGTERM),
        (101, signal.SIGTERM),
        (101, signal.SIGKILL),
    }
