from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def ensure_cached_url(
    *,
    url: str,
    target: Path,
    timeout_seconds: float = 60,
    user_agent: str = "benchmark-core/0.1",
) -> Path:
    if not url.strip():
        raise ValueError("url must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size > 0:
        return target

    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        target.write_bytes(response.read())

    if target.stat().st_size <= 0:
        raise ValueError(f"Downloaded dataset source is empty: {url}")
    return target
