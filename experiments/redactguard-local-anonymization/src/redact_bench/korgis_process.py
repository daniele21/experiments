from __future__ import annotations

import os
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


def run_korgis_cli(
    repo: Path,
    *args: str,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["uv", "run", "--frozen", "local-llm", *args]
    try:
        return subprocess.run(
            command,
            cwd=repo,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() if capture_output else ""
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(
            f"Korgis command failed with exit code {exc.returncode}: "
            + " ".join(command)
            + suffix
        ) from exc


def inspect_korgis_models(repo: Path, models: list[str]) -> dict[str, dict]:
    code = (
        "import json,sys;"
        "from local_llm_server import list_models;"
        "wanted=set(sys.argv[1:]);"
        "items=[{'key':m['key'],'downloaded':bool(m['downloaded']),"
        "'path':str(m['path']),'source':m.get('source'),'backend':m.get('backend')} "
        "for m in list_models() if m['key'] in wanted];"
        "print(json.dumps(items))"
    )
    command = ["uv", "run", "--frozen", "python", "-c", code, *models]
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise RuntimeError(
            "Could not inspect Korgis local model inventory"
            + (f": {detail}" if detail else "")
        ) from exc

    items = json.loads(completed.stdout)
    inventory = {str(item["key"]): item for item in items}

    unknown = [model for model in models if model not in inventory]
    if unknown:
        raise ValueError(
            "Models are not present in the active Korgis registry: "
            + ", ".join(unknown)
        )
    return inventory


def prepare_korgis_models(
    repo: Path,
    models: list[str],
    *,
    download_missing: bool = False,
) -> dict[str, dict]:
    inventory = inspect_korgis_models(repo, models)
    missing = [
        model
        for model in models
        if not bool(inventory[model].get("downloaded"))
    ]

    if missing and download_missing:
        for model in missing:
            run_korgis_cli(repo, "download", model)
        inventory = inspect_korgis_models(repo, models)
        missing = [
            model
            for model in models
            if not bool(inventory[model].get("downloaded"))
        ]

    if missing:
        details = "\n".join(
            f"  - {model}: {inventory[model].get('path')}"
            for model in missing
        )
        raise FileNotFoundError(
            "Required Korgis model artifacts are not available locally:\n"
            f"{details}\n"
            "The managed suite does not download models by default. "
            "Install/configure the artifacts in Korgis, or rerun with "
            "--download-missing if you explicitly want network downloads."
        )

    return inventory


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
        command = [
            "uv",
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
