"""korgis_manager.py.

Robust lifecycle manager for the local Korgis (local-llm-server) instance.
Handles:
  - Checking and automatically freeing ports 1235 and 8091 from stale processes.
  - Launching Korgis as a dedicated process group with file-backed logging.
  - Fast-failing immediately if Korgis exits unexpectedly.
  - Activating/swapping models sequentially via the Korgis Admin API.
  - Unloading models to free RAM/VRAM between runs.
  - Clean process-group termination on shutdown or interrupt.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _free_port(port: int) -> None:
    """Terminate any lingering process bound to the specified TCP port."""
    try:
        out = subprocess.check_output(
            ["lsof", "-t", f"-i:{port}"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        for pid_str in out.split():
            if pid_str.isdigit():
                pid = int(pid_str)
                logger.info("Found process PID %s on port %s; terminating...", pid, port)
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    except Exception:
        pass


def _clean_lingering_llama_servers() -> None:
    """Terminate any orphan llama-server processes left from previous interrupted runs."""
    try:
        subprocess.run(["pkill", "-9", "llama-server"], stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


class KorgisManager:
    """Manages connection and subprocess lifecycle for Korgis."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1235/v1",
        korgis_dir: str | Path | None = None,
        registry_path: str | Path | None = None,
        log_file: str | Path = "results/logs/korgis.log",
        timeout: float = 360.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.root_url = self.base_url.removesuffix("/v1")
        if korgis_dir:
            self.korgis_dir = Path(korgis_dir).resolve()
        else:
            candidates = [
                Path(__file__).resolve().parents[3] / "korgis",
                Path(__file__).resolve().parents[2] / "korgis",
                Path.home() / "Personal" / "experiments" / "korgis",
            ]
            self.korgis_dir = next((c for c in candidates if c.is_dir()), candidates[0])
        self.registry_path = Path(registry_path).resolve() if registry_path else None
        self.log_path = Path(log_file).resolve()
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self.log_handle: Any = None
        self.started_by_us = False

        # Register cleanup on exit
        atexit.register(self.stop_server)

    def is_healthy(self) -> bool:
        """Check if Korgis /health responds with 200 OK."""
        try:
            req = urllib.request.Request(f"{self.root_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return bool(data.get("ok"))
        except Exception:
            return False

    def wait_for_healthy(self, max_wait: float = 45.0, poll_interval: float = 1.0) -> bool:
        """Wait until Korgis responds to health checks or fast-fail if the process exits."""
        started = time.time()
        while time.time() - started < max_wait:
            if self.process and self.process.poll() is not None:
                err_tail = self._read_log_tail(15)
                raise RuntimeError(
                    f"Korgis process died unexpectedly with code {self.process.returncode}.\n"
                    f"Last log lines ({self.log_path}):\n{err_tail}"
                )
            if self.is_healthy():
                return True
            time.sleep(poll_interval)
        return False

    def ensure_running(self, initial_model: str) -> bool:
        """Ensure Korgis is running and ready.

        If already running, returns True. Otherwise, starts it as a background process.
        """
        if self.is_healthy():
            logger.info("Korgis is already active at %s", self.root_url)
            return True

        # Pre-flight: make sure standard ports (1235 for Korgis, 8091 for llama-server) are free
        _free_port(1235)
        _free_port(8091)
        _clean_lingering_llama_servers()

        logger.info("Starting Korgis server with initial model '%s'...", initial_model)
        env = os.environ.copy()

        # Explicitly ensure LOCAL_LLM_SERVER_BIN points to the validated llama-server binary
        if "LOCAL_LLM_SERVER_BIN" not in env:
            discovered_bin = shutil.which("llama-server") or "/opt/homebrew/bin/llama-server"
            if Path(discovered_bin).is_file():
                env["LOCAL_LLM_SERVER_BIN"] = str(discovered_bin)

        # Ensure PATH includes /opt/homebrew/bin and local bin directories
        current_path = env.get("PATH", "")
        if "/opt/homebrew/bin" not in current_path:
            env["PATH"] = f"/opt/homebrew/bin:{current_path}"

        # For structured decision benchmarks, disable thinking traces so models output direct JSON
        # instead of exhausting max_tokens in <think> tags (which leaves content empty -> 502 invalid_model_output).
        if "LLAMA_ARG_REASONING" not in env:
            env["LLAMA_ARG_REASONING"] = "off"
        if self.registry_path and self.registry_path.is_file():
            env["LOCAL_LLM_REGISTRY_PATHS"] = str(self.registry_path)

        cmd = [
            "uv", "run", "--frozen", "local-llm", "serve",
            "--model", initial_model,
            "--enable-admin-api",
            "--no-download",
        ]

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("w", encoding="utf-8")

        # start_new_session=True creates a new process group so child processes (like llama-server)
        # can be terminated together reliably.
        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.korgis_dir),
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.started_by_us = True

        logger.info("Waiting for Korgis to initialize (log: %s)...", self.log_path)
        if not self.wait_for_healthy(max_wait=self.timeout):
            self.stop_server()
            err_tail = self._read_log_tail(15)
            raise RuntimeError(
                f"Korgis failed to become healthy within {self.timeout}s.\n"
                f"Last log output:\n{err_tail}"
            )

        logger.info("Korgis successfully started and healthy.")
        return True

    def activate_model(self, model_key: str) -> dict[str, Any]:
        """Activate a model sequentially via Korgis Admin API."""
        logger.info("Activating model '%s' in Korgis...", model_key)
        payload = json.dumps({"model": model_key}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.root_url}/api/v1/models/activate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            logger.info("Model '%s' active: %s", model_key, data.get("ok"))
            return data

    def unload_model(self, model_key: str) -> dict[str, Any]:
        """Unload a model from memory via Korgis Admin API."""
        logger.info("Unloading model '%s' from Korgis memory...", model_key)
        try:
            req = urllib.request.Request(
                f"{self.root_url}/api/v1/models/{model_key}",
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                logger.info("Model '%s' unloaded.", model_key)
                return data
        except Exception as exc:
            logger.warning("Unload request for '%s' returned: %s", model_key, exc)
            return {"ok": False, "error": str(exc)}

    def resident_models(self) -> set[str]:
        """List currently resident model keys."""
        try:
            req = urllib.request.Request(f"{self.base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                keys = set()
                for item in payload.get("data", []):
                    for k in ("key", "id"):
                        if item.get(k):
                            keys.add(str(item[k]))
                return keys
        except Exception:
            return set()

    def stop_server(self) -> None:
        """Terminate the server process group if started by us."""
        if self.process and self.started_by_us:
            pid = self.process.pid
            logger.info("Stopping Korgis server process group (PGID %s)...", pid)
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                time.sleep(1.0)
                if self.process.poll() is None:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                pass
            self.process = None
            self.started_by_us = False

        if self.log_handle and not self.log_handle.closed:
            self.log_handle.close()

        # Ensure ports and child processes are completely clean
        _free_port(1235)
        _free_port(8091)
        _clean_lingering_llama_servers()
        logger.info("Korgis server and worker runtimes stopped.")

    def _read_log_tail(self, lines: int = 15) -> str:
        """Read the last N lines of the server log file."""
        if not self.log_path.is_file():
            return "No log file found."
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(content[-lines:])
        except Exception as exc:
            return f"Error reading log: {exc}"
