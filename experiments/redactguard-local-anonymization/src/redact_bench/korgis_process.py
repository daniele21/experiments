from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from redact_bench.provider import KorgisController, KorgisUnavailableError


KORGIS_REPO_NAMES = ("korgis", "local-llm-server")


def _looks_like_korgis_repo(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "pyproject.toml").is_file()
        and (path / "src/local_llm_server").is_dir()
    )


def resolve_korgis_repo(
    explicit: str | Path | None = None,
    *,
    experiment_root: Path | None = None,
) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not _looks_like_korgis_repo(candidate):
            raise ValueError(
                f"Not a Korgis repository: {candidate}. "
                "Expected pyproject.toml and src/local_llm_server/."
            )
        return candidate

    env_value = os.getenv("KORGIS_REPO")
    if env_value:
        return resolve_korgis_repo(env_value, experiment_root=experiment_root)

    starts = [Path.cwd().resolve()]
    if experiment_root is not None:
        starts.append(experiment_root.resolve())

    seen: set[Path] = set()
    for start in starts:
        for ancestor in (start, *start.parents):
            for name in KORGIS_REPO_NAMES:
                candidate = (ancestor / name).resolve()
                if candidate in seen:
                    continue
                seen.add(candidate)
                if _looks_like_korgis_repo(candidate):
                    return candidate

    raise ValueError(
        "Korgis repository not found. Pass --korgis-repo /path/to/korgis "
        "or set KORGIS_REPO."
    )


def korgis_git_sha(repo: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _find_uv_binary(env: dict[str, str] | None = None) -> str:
    path_val = env.get("PATH") if env else None
    discovered = shutil.which("uv", path=path_val)
    if discovered:
        return discovered
    for candidate in (
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "uv"


def _clean_korgis_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment isolated from the benchmark runner virtualenv."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONHOME", None)

    # Ensure standard user and package binary paths are present in PATH
    current_paths = env.get("PATH", "").split(os.pathsep)
    paths_to_add: list[str] = []
    for candidate_dir in (
        Path.home() / ".local" / "bin",
        Path.home() / ".cargo" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ):
        cand_str = str(candidate_dir)
        if candidate_dir.is_dir() and cand_str not in current_paths:
            paths_to_add.append(cand_str)
    if paths_to_add:
        env["PATH"] = os.pathsep.join([*paths_to_add, *current_paths])

    if "LOCAL_LLM_SERVER_BIN" not in env:
        discovered = shutil.which("llama-server", path=env.get("PATH"))
        if not discovered:
            for candidate in (
                Path("/opt/homebrew/bin/llama-server"),
                Path("/usr/local/bin/llama-server"),
                Path.home() / ".local" / "bin" / "llama-server",
            ):
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    discovered = str(candidate)
                    break
        if discovered:
            env["LOCAL_LLM_SERVER_BIN"] = discovered
    if extra_env:
        env.update(extra_env)
    return env


def run_korgis_cli(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cleaned_env = _clean_korgis_env(env)
    uv_bin = _find_uv_binary(cleaned_env)
    command = [uv_bin, "run", "--frozen", "local-llm", *args]
    return subprocess.run(
        command,
        cwd=repo,
        check=True,
        text=True,
        env=cleaned_env,
    )


def ensure_korgis_models(repo: Path, models: list[str]) -> None:
    for model in models:
        run_korgis_cli(repo, "download", model)


class ManagedKorgis:
    def __init__(
        self,
        *,
        repo: Path,
        anchor_model: str,
        log_path: Path,
        startup_timeout_seconds: float = 600.0,
        api_base: str | None = None,
        reuse_existing: bool = False,
    ) -> None:
        self.repo = repo
        self.anchor_model = anchor_model
        self.log_path = log_path
        self.startup_timeout_seconds = startup_timeout_seconds
        self.controller = KorgisController(api_base)
        self.reuse_existing = reuse_existing
        self.process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self.reused_existing = False

    def __enter__(self) -> "ManagedKorgis":
        if self._server_is_healthy():
            if not self.reuse_existing:
                raise RuntimeError(
                    f"Korgis is already running at {self.controller.api_base}. "
                    "The managed suite requires an isolated port; stop that server or "
                    "change suite.korgis_base_url."
                )
            self._assert_admin_api()
            self.reused_existing = True
            return self

        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _server_is_healthy(self) -> bool:
        try:
            self.controller.health()
            return True
        except KorgisUnavailableError:
            return False

    def _assert_admin_api(self) -> None:
        try:
            self.controller.registry()
        except Exception as exc:
            raise RuntimeError(
                "A Korgis server is reachable but its admin API is unavailable. "
                "Restart it with --enable-admin-api."
            ) from exc

    def start(self) -> None:
        parsed = urlparse(self.controller.api_base)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1235

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self.log_path.open("w", encoding="utf-8")
        cleaned_env = _clean_korgis_env()
        uv_bin = _find_uv_binary(cleaned_env)
        command = [
            uv_bin,
            "run",
            "--frozen",
            "local-llm",
            "serve",
            "--model",
            self.anchor_model,
            "--enable-admin-api",
            "--no-download",
            "--host",
            host,
            "--port",
            str(port),
        ]
        self.process = subprocess.Popen(
            command,
            cwd=self.repo,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            env=cleaned_env,
        )
        self._wait_until_ready()
        self._assert_admin_api()

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    "Korgis exited during startup. Last log lines:\n"
                    + self.tail_log()
                )
            if self._server_is_healthy():
                return
            time.sleep(2)

        self.stop()
        raise TimeoutError(
            f"Korgis did not become healthy within {self.startup_timeout_seconds:.0f}s. "
            f"See {self.log_path}."
        )

    def stop(self) -> None:
        if self.process is not None and not self.reused_existing:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None

        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def tail_log(self, lines: int = 40) -> str:
        if self._log_handle is not None:
            self._log_handle.flush()
        if not self.log_path.exists():
            return "<no Korgis log>"
        content = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
