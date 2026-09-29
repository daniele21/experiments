from __future__ import annotations

import atexit
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark_core.config import load_yaml_mapping


@dataclass(frozen=True)
class CLMLocalRuntimeSpec:
    runtime_id: str
    benchmark_model_id: str
    served_model: str
    head_model_id: str
    head_checkpoint_env: str
    encoder_model_id: str
    encoder_filename: str
    encoder_path_env: str
    encoder_format: str
    encoder_quantization: str
    output_weight_quantization: str | None
    encoder_backend: str
    encoder_alias: str
    pooling: str
    context_size: int
    parallel: int
    max_tokens: int
    encoder_host: str
    encoder_port: int
    clm_host: str
    clm_port: int
    tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(
        cls,
        runtime_id: str,
        payload: dict[str, Any],
    ) -> "CLMLocalRuntimeSpec":
        head = payload.get("head") or {}
        encoder = payload.get("encoder") or {}
        clm = payload.get("clm") or {}
        if not isinstance(head, dict) or not isinstance(encoder, dict) or not isinstance(clm, dict):
            raise TypeError(f"{runtime_id}: head, encoder and clm must be mappings")

        spec = cls(
            runtime_id=runtime_id,
            benchmark_model_id=str(payload.get("benchmark_model_id") or runtime_id),
            served_model=str(payload.get("served_model") or "clm-latest"),
            head_model_id=str(head.get("model_id") or "Contrastive-LM/CLM-v0.1-8B"),
            head_checkpoint_env=str(head.get("checkpoint_env") or "CLM_CKPT"),
            encoder_model_id=str(encoder["model_id"]),
            encoder_filename=str(encoder["filename"]),
            encoder_path_env=str(encoder.get("path_env") or "CLM_ENCODER_GGUF"),
            encoder_format=str(encoder.get("format") or "gguf"),
            encoder_quantization=str(encoder["quantization"]),
            output_weight_quantization=(
                str(encoder["output_weight_quantization"])
                if encoder.get("output_weight_quantization")
                else None
            ),
            encoder_backend=str(encoder.get("backend") or "llama-server"),
            encoder_alias=str(encoder.get("alias") or "qwen3-8b"),
            pooling=str(encoder.get("pooling") or "last"),
            context_size=int(encoder.get("context_size") or 8192),
            parallel=int(encoder.get("parallel") or 4),
            max_tokens=int(clm.get("max_tokens") or 2048),
            encoder_host=str(clm.get("encoder_host") or "127.0.0.1"),
            encoder_port=int(clm.get("encoder_port") or 8090),
            clm_host=str(clm.get("host") or "127.0.0.1"),
            clm_port=int(clm.get("port") or 8700),
            tags=tuple(str(tag) for tag in (payload.get("tags") or [])),
        )
        if spec.encoder_format != "gguf":
            raise ValueError(f"{runtime_id}: managed CLM runtime currently requires GGUF")
        if spec.pooling != "last":
            raise ValueError(f"{runtime_id}: CLM-v0.1-8B requires last-token pooling")
        if spec.context_size <= 0 or spec.parallel <= 0 or spec.max_tokens <= 0:
            raise ValueError(
                f"{runtime_id}: context_size, parallel and max_tokens must be positive"
            )
        if spec.context_size < spec.parallel * spec.max_tokens:
            raise ValueError(
                f"{runtime_id}: context_size ({spec.context_size}) must be at least "
                f"parallel * max_tokens ({spec.parallel * spec.max_tokens})"
            )
        return spec


def load_clm_runtime_spec(path: Path, runtime_id: str) -> CLMLocalRuntimeSpec:
    payload = load_yaml_mapping(path)
    runtimes = payload.get("runtimes")
    if not isinstance(runtimes, dict):
        raise ValueError(f"{path}: missing runtimes mapping")
    raw = runtimes.get(runtime_id)
    if not isinstance(raw, dict):
        available = ", ".join(sorted(str(key) for key in runtimes)) or "<none>"
        raise ValueError(
            f"Unknown CLM runtime {runtime_id!r}. Available: {available}"
        )
    return CLMLocalRuntimeSpec.from_mapping(runtime_id, raw)


class CLMLocalRuntimeManager:
    """Own a local llama.cpp embeddings server plus clm-serve process.

    The benchmark owns only processes it starts. Existing listeners are never
    killed or replaced; occupied ports fail fast to avoid disrupting unrelated
    local services.
    """

    def __init__(
        self,
        spec: CLMLocalRuntimeSpec,
        *,
        encoder_path: Path | None = None,
        llama_server_bin: str | None = None,
        clm_serve_bin: str | None = None,
        clm_checkpoint: Path | None = None,
        startup_timeout: float = 300.0,
        log_dir: Path = Path("results/logs"),
    ) -> None:
        self.spec = spec
        self.encoder_path = encoder_path
        self.llama_server_bin = llama_server_bin
        self.clm_serve_bin = clm_serve_bin
        self.clm_checkpoint = clm_checkpoint
        self.startup_timeout = startup_timeout
        self.log_dir = log_dir
        self.encoder_process: subprocess.Popen[str] | None = None
        self.clm_process: subprocess.Popen[str] | None = None
        self._log_handles: list[Any] = []
        self._stop_on_exit = True
        self._registered = False

    @property
    def embeddings_url(self) -> str:
        return (
            f"http://{self.spec.encoder_host}:{self.spec.encoder_port}"
            "/v1/embeddings"
        )

    @property
    def clm_base_url(self) -> str:
        return f"http://{self.spec.clm_host}:{self.spec.clm_port}"

    @staticmethod
    def _resolve_executable(
        explicit: str | None,
        env_names: tuple[str, ...],
        fallback: str,
    ) -> str:
        candidates: list[str] = []
        if explicit:
            candidates.append(explicit)
        for name in env_names:
            value = os.getenv(name)
            if value:
                candidates.append(value)
        candidates.append(fallback)

        for candidate in candidates:
            if os.sep in candidate or (os.altsep and os.altsep in candidate):
                path = Path(candidate).expanduser()
                if path.is_file() and os.access(path, os.X_OK):
                    return str(path.resolve())
                continue
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        raise RuntimeError(
            f"Executable {fallback!r} not found. Checked explicit setting, "
            f"{', '.join(env_names)} and PATH."
        )

    def _resolve_encoder_path(self) -> Path:
        raw = self.encoder_path or (
            Path(os.environ[self.spec.encoder_path_env]).expanduser()
            if os.getenv(self.spec.encoder_path_env)
            else None
        )
        if raw is None:
            raise RuntimeError(
                f"Encoder GGUF path is required. Set {self.spec.encoder_path_env} "
                "or pass --encoder-path."
            )
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"Encoder GGUF does not exist: {path}")
        if path.name != self.spec.encoder_filename:
            raise RuntimeError(
                f"Runtime {self.spec.runtime_id!r} expects "
                f"{self.spec.encoder_filename!r}, got {path.name!r}."
            )
        return path

    def _resolve_checkpoint(self) -> Path | None:
        raw: Path | None = self.clm_checkpoint
        if raw is None:
            value = os.getenv(self.spec.head_checkpoint_env)
            if value:
                raw = Path(value)
        if raw is None:
            return None
        path = raw.expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"CLM checkpoint does not exist: {path}")
        return path

    @staticmethod
    def _assert_port_free(host: str, port: int) -> None:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError as exc:
                raise RuntimeError(
                    f"Port {host}:{port} is already in use; managed CLM runtime "
                    "will not terminate or replace existing processes."
                ) from exc

    @staticmethod
    def _http_json(url: str, timeout: float = 2.0) -> dict[str, Any] | None:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _process_error(process: subprocess.Popen[str] | None, name: str) -> str | None:
        if process is not None and process.poll() is not None:
            return f"{name} exited with code {process.returncode}"
        return None

    def encoder_command(
        self,
        *,
        encoder_path: Path,
        llama_server_bin: str,
    ) -> list[str]:
        return [
            llama_server_bin,
            "--model",
            str(encoder_path),
            "--embedding",
            "--pooling",
            self.spec.pooling,
            "--alias",
            self.spec.encoder_alias,
            "--host",
            self.spec.encoder_host,
            "--port",
            str(self.spec.encoder_port),
            "--ctx-size",
            str(self.spec.context_size),
            "--parallel",
            str(self.spec.parallel),
        ]

    def clm_command(
        self,
        *,
        clm_serve_bin: str,
        checkpoint: Path | None,
    ) -> list[str]:
        command = [
            clm_serve_bin,
            "--port",
            str(self.spec.clm_port),
            "--emb-url",
            self.embeddings_url,
            "--emb-model",
            self.spec.encoder_alias,
            "--max-tokens",
            str(self.spec.max_tokens),
            "--no-ui",
        ]
        if checkpoint is not None:
            command.extend(["--ckpt", str(checkpoint)])
        return command

    def _spawn(self, name: str, command: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"{name}.log"
        handle = log_path.open("a", encoding="utf-8")
        self._log_handles.append(handle)
        handle.write("\n=== START " + time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
        handle.write("command: " + " ".join(command) + "\n")
        handle.flush()
        return subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )

    def _wait_for_encoder(self) -> None:
        deadline = time.monotonic() + self.startup_timeout
        url = f"http://{self.spec.encoder_host}:{self.spec.encoder_port}/v1/models"
        while time.monotonic() < deadline:
            error = self._process_error(self.encoder_process, "llama-server")
            if error:
                raise RuntimeError(error)
            if self._http_json(url) is not None:
                return
            time.sleep(0.5)
        raise RuntimeError(
            f"Timed out waiting for llama-server at {url} after "
            f"{self.startup_timeout:.0f}s"
        )

    def _wait_for_clm(self) -> dict[str, Any]:
        deadline = time.monotonic() + self.startup_timeout
        url = f"{self.clm_base_url}/health"
        last: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            error = self._process_error(self.clm_process, "clm-serve")
            if error:
                raise RuntimeError(error)
            last = self._http_json(url)
            if last and last.get("ok") and last.get("embedder"):
                return last
            time.sleep(0.5)
        raise RuntimeError(
            f"Timed out waiting for healthy clm-serve at {url}; last health={last}"
        )

    def start(self) -> dict[str, Any]:
        if self.encoder_process is not None or self.clm_process is not None:
            raise RuntimeError("Managed CLM runtime has already been started")
        if self.startup_timeout <= 0:
            raise ValueError("startup_timeout must be positive")

        encoder_path = self._resolve_encoder_path()
        checkpoint = self._resolve_checkpoint()
        llama_bin = self._resolve_executable(
            self.llama_server_bin,
            ("CLM_LLAMA_SERVER_BIN", "LOCAL_LLM_SERVER_BIN"),
            "llama-server",
        )
        clm_bin = self._resolve_executable(
            self.clm_serve_bin,
            ("CLM_SERVE_BIN",),
            "clm-serve",
        )

        self._assert_port_free(self.spec.encoder_host, self.spec.encoder_port)
        self._assert_port_free(self.spec.clm_host, self.spec.clm_port)

        if not self._registered:
            atexit.register(self.stop)
            self._registered = True

        env = os.environ.copy()
        try:
            self.encoder_process = self._spawn(
                f"clm-encoder-{self.spec.runtime_id}",
                self.encoder_command(
                    encoder_path=encoder_path,
                    llama_server_bin=llama_bin,
                ),
                env,
            )
            self._wait_for_encoder()

            self.clm_process = self._spawn(
                f"clm-serve-{self.spec.runtime_id}",
                self.clm_command(
                    clm_serve_bin=clm_bin,
                    checkpoint=checkpoint,
                ),
                env,
            )
            health = self._wait_for_clm()
        except Exception:
            self.stop()
            raise

        return self.identity(
            encoder_path=encoder_path,
            checkpoint=checkpoint,
            health=health,
        )

    def identity(
        self,
        *,
        encoder_path: Path | None = None,
        checkpoint: Path | None = None,
        health: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if encoder_path is None:
            encoder_path = self._resolve_encoder_path()
        stat = encoder_path.stat()
        return {
            "runtime_id": self.spec.runtime_id,
            "benchmark_model_id": self.spec.benchmark_model_id,
            "served_model": self.spec.served_model,
            "head": {
                "model_id": self.spec.head_model_id,
                "checkpoint": str(checkpoint) if checkpoint is not None else "upstream-default",
            },
            "encoder": {
                "model_id": self.spec.encoder_model_id,
                "filename": self.spec.encoder_filename,
                "path": str(encoder_path),
                "size_bytes": stat.st_size,
                "format": self.spec.encoder_format,
                "quantization": self.spec.encoder_quantization,
                "output_weight_quantization": self.spec.output_weight_quantization,
                "backend": self.spec.encoder_backend,
                "alias": self.spec.encoder_alias,
                "pooling": self.spec.pooling,
                "context_size": self.spec.context_size,
                "parallel": self.spec.parallel,
            },
            "endpoints": {
                "embeddings": self.embeddings_url,
                "clm": self.clm_base_url,
            },
            "health": health or {},
            "tags": list(self.spec.tags),
        }

    def detach(self) -> None:
        """Leave owned processes running after the benchmark process exits."""
        self._stop_on_exit = False

    @staticmethod
    def _terminate(process: subprocess.Popen[str] | None) -> None:
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if process.poll() is None:
                try:
                    if os.name == "posix":
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass

    def stop(self) -> None:
        if not self._stop_on_exit:
            return
        self._terminate(self.clm_process)
        self._terminate(self.encoder_process)
        self.clm_process = None
        self.encoder_process = None
        for handle in self._log_handles:
            try:
                handle.close()
            except OSError:
                pass
        self._log_handles.clear()
