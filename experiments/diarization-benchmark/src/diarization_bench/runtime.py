from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from .config import ModelSpec


@dataclass(frozen=True)
class RuntimeResult:
    payload: dict
    wall_seconds: float
    peak_rss_mb: float
    cpu_seconds: float
    stderr: str


class FluidAudioRuntime:
    def __init__(self, experiment_root: Path) -> None:
        self.experiment_root = experiment_root
        self.package_path = experiment_root / "runtime" / "fluidaudio-helper"
        self.binary_path = self.package_path / ".build" / "release" / "diarization-helper"

    def preflight(self) -> list[str]:
        problems: list[str] = []
        if shutil.which("swift") is None:
            problems.append("swift is not on PATH")
        if os.uname().sysname != "Darwin":
            problems.append("real FluidAudio execution requires macOS")
        if not self.package_path.exists():
            problems.append(f"missing Swift helper package: {self.package_path}")
        return problems

    def build(self) -> None:
        subprocess.run(
            ["swift", "build", "-c", "release", "--package-path", str(self.package_path)],
            check=True,
        )

    def run(self, model: ModelSpec, audio: Path) -> RuntimeResult:
        if not self.binary_path.exists():
            raise FileNotFoundError(
                f"{self.binary_path} does not exist; run 'diarization-bench build-helper' first"
            )

        command = [
            str(self.binary_path),
            "--engine",
            model.engine,
            "--audio",
            str(audio),
        ]
        for key, value in model.options.items():
            if value is None or key == "profile":
                continue
            command.extend([f"--{key}", str(value).lower() if isinstance(value, bool) else str(value)])

        started = time.perf_counter()
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        ps_proc = psutil.Process(proc.pid)
        peak_rss = 0
        last_cpu = 0.0

        while proc.poll() is None:
            try:
                peak_rss = max(peak_rss, ps_proc.memory_info().rss)
                times = ps_proc.cpu_times()
                last_cpu = times.user + times.system
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            time.sleep(0.05)

        stdout, stderr = proc.communicate()
        wall = time.perf_counter() - started
        if proc.returncode != 0:
            raise RuntimeError(stderr.strip() or stdout.strip() or f"helper exited {proc.returncode}")

        payload = None
        for line in reversed(stdout.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and "segments" in candidate:
                payload = candidate
                break
        if payload is None:
            raise RuntimeError(f"helper returned no JSON payload; stdout={stdout!r}")

        return RuntimeResult(
            payload=payload,
            wall_seconds=wall,
            peak_rss_mb=peak_rss / (1024 * 1024),
            cpu_seconds=last_cpu,
            stderr=stderr,
        )
