from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core.contracts.media import MediaRef, MediaType, OutputArtifact


class ArtifactStoreError(ValueError):
    """Raised when a benchmark media artifact cannot be persisted or registered."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extension_for_mime(mime_type: str) -> str:
    explicit = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return explicit.get(mime_type) or mimetypes.guess_extension(mime_type) or ".bin"


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def persist_bytes(
        self,
        *,
        artifact_id: str,
        media_type: MediaType,
        data: bytes,
        mime_type: str,
        width: int | None = None,
        height: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OutputArtifact:
        if not data:
            raise ArtifactStoreError("artifact data must not be empty")

        digest = sha256_bytes(data)
        destination = self.root / f"{digest}{_extension_for_mime(mime_type)}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)

        return OutputArtifact(
            artifact_id=artifact_id,
            media_type=media_type,
            path=str(destination),
            mime_type=mime_type,
            sha256=digest,
            width=width,
            height=height,
            size_bytes=len(data),
            metadata=dict(metadata or {}),
        )

    def register_input(
        self,
        *,
        path: str | Path,
        media_id: str,
        media_type: MediaType,
        mime_type: str | None = None,
        width: int | None = None,
        height: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MediaRef:
        source = Path(path)
        if not source.is_file():
            raise ArtifactStoreError(f"media file does not exist: {source}")

        resolved_mime = mime_type or mimetypes.guess_type(source.name)[0]
        if resolved_mime is None:
            raise ArtifactStoreError(f"cannot infer MIME type for media file: {source}")

        return MediaRef(
            media_id=media_id,
            media_type=media_type,
            location=str(source),
            mime_type=resolved_mime,
            sha256=sha256_file(source),
            width=width,
            height=height,
            metadata=dict(metadata or {}),
        )
