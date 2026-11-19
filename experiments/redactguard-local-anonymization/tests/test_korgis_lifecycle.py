import subprocess
import sys
import time

import pytest

from redact_bench.korgis_process import ManagedKorgis


def test_stop_closes_runtime_in_separate_session(tmp_path):
    ready = tmp_path / "ready"
    stopped = tmp_path / "stopped"
    runtime = (
        "import signal,time; from pathlib import Path; "
        f"signal.signal(signal.SIGTERM, lambda *_: (Path({str(stopped)!r}).touch(), exit(0))); "
        f"Path({str(ready)!r}).touch(); time.sleep(60)"
    )
    wrapper = (
        "import subprocess,sys,time; "
        f"p=subprocess.Popen([sys.executable,'-c',{runtime!r}],start_new_session=True); "
        "p.wait()"
    )
    process = subprocess.Popen([sys.executable, "-c", wrapper])
    server = ManagedKorgis(repo=tmp_path, anchor_model="test", log_path=tmp_path / "log")
    server.process = process
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        server.stop()
        deadline = time.monotonic() + 5
        while not stopped.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert stopped.exists(), "runtime must receive shutdown even in its own session"
        assert process.poll() is not None
    finally:
        server.stop()


def test_stop_force_kills_stubborn_runtime_and_preserves_unrelated_process(tmp_path):
    from redact_bench.korgis_process import _process_snapshot

    ready = tmp_path / "runtime.pid"
    runtime = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    wrapper = (
        "import subprocess,sys; "
        f"subprocess.Popen([sys.executable,'-c',{runtime!r}],start_new_session=True).wait()"
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    process = subprocess.Popen([sys.executable, "-c", wrapper])
    server = ManagedKorgis(repo=tmp_path, anchor_model="test", log_path=tmp_path / "log")
    server.process = process
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        pid = int(ready.read_text())
        server.stop()
        entry = _process_snapshot().get(pid)
        assert entry is None or "Z" in entry[1]
        assert unrelated.poll() is None
    finally:
        server.stop()
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_failed_start_cleans_up_and_closes_log(tmp_path, monkeypatch):
    server = ManagedKorgis(repo=tmp_path, anchor_model="test", log_path=tmp_path / "log")
    monkeypatch.setattr(server, "_server_is_healthy", lambda: False)
    process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    handle = (tmp_path / "log").open("w")

    def failed_start():
        server.process = process
        server._log_handle = handle
        raise TimeoutError("startup failed")

    monkeypatch.setattr(server, "start", failed_start)
    try:
        with pytest.raises(TimeoutError, match="startup failed"):
            server.__enter__()
        assert process.poll() is not None
        assert handle.closed
    finally:
        server.stop()
