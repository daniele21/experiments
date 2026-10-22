"""Single-file public dashboard data, published with atomic replacement."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PRIVATE_KEYS = {
    "source_dir", "cwd", "executable", "model_path", "mmproj_path", "artifact_path",
    "llama_server_bin", "local_path", "home", "hostname", "username", "user_name",
    "environ", "environment_variables", "api_key", "authorization", "password",
    "secret", "access_token", "refresh_token", "hf_token", "api_token", "auth_token",
    "bearer_token", "token",
}
_LOCAL_PATH = re.compile(r"(?:/Users/|/home/|/private/|/var/|/tmp/|[A-Za-z]:[\\/])")


def public_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            name = key.lower()
            if name in _PRIVATE_KEYS or name.endswith(("_api_key", "_password", "_secret")):
                clean[key] = None
            elif name.endswith("_json") and isinstance(item, str):
                try:
                    decoded = json.loads(item)
                except json.JSONDecodeError:
                    clean[key] = public_value(item)
                else:
                    clean[key] = json.dumps(public_value(decoded), sort_keys=True)
            else:
                clean[key] = public_value(item)
        return clean
    if isinstance(value, list):
        return [public_value(item) for item in value]
    if isinstance(value, str) and (
        _LOCAL_PATH.search(value) or re.search(r"https?://[^/\s]+:[^/\s]+@", value)
    ):
        return "[redacted local or credential-bearing value]"
    return value


def write_public_bundle(data_dir: Path, *, destination: Path) -> Path:
    """Read only files referenced by this export's index, excluding stale files."""
    index = json.loads((data_dir / "index.json").read_text())

    def read(relative: str) -> Any:
        path = (data_dir / relative).resolve()
        if not path.is_relative_to(data_dir.resolve()):
            raise ValueError("Dashboard index references a file outside its export directory")
        return json.loads(path.read_text())

    bundle = public_value({
        "schema_version": "1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "overview": read(index["overview"]),
        **{section: {key: read(relative) for key, relative in index[section].items()}
           for section in ("capabilities", "models", "runs")},
    })
    # Serialize first: failures must leave the previously published file intact.
    content = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
