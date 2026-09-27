from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

MediaType = Literal["image", "video", "audio", "document"]
ContentPartKind = Literal["text", "image", "video", "audio", "document"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_dimensions(width: int | None, height: int | None) -> None:
    if width is not None and width <= 0:
        raise ValueError("width must be > 0")
    if height is not None and height <= 0:
        raise ValueError("height must be > 0")


@dataclass(frozen=True)
class MediaRef:
    media_id: str
    media_type: MediaType
    location: str
    mime_type: str
    sha256: str
    width: int | None = None
    height: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.media_id, "media_id")
        _require_non_empty(self.location, "location")
        _require_non_empty(self.mime_type, "mime_type")
        normalized_sha = self.sha256.lower()
        if not _SHA256_RE.fullmatch(normalized_sha):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        object.__setattr__(self, "sha256", normalized_sha)
        _validate_dimensions(self.width, self.height)
        if self.media_type == "image" and not self.mime_type.startswith("image/"):
            raise ValueError("image media requires an image/* MIME type")


@dataclass(frozen=True)
class ContentPart:
    kind: ContentPartKind
    text: str | None = None
    media: MediaRef | None = None

    def __post_init__(self) -> None:
        if self.kind == "text":
            if self.text is None or not self.text.strip():
                raise ValueError("text content parts require non-empty text")
            if self.media is not None:
                raise ValueError("text content parts cannot include media")
            return

        if self.media is None:
            raise ValueError(f"{self.kind} content parts require media")
        if self.text is not None:
            raise ValueError(f"{self.kind} content parts cannot include text")
        if self.media.media_type != self.kind:
            raise ValueError(
                f"content part kind {self.kind!r} does not match media type "
                f"{self.media.media_type!r}"
            )


@dataclass(frozen=True)
class OutputArtifact:
    artifact_id: str
    media_type: MediaType
    path: str
    mime_type: str
    sha256: str
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.artifact_id, "artifact_id")
        _require_non_empty(self.path, "path")
        _require_non_empty(self.mime_type, "mime_type")
        normalized_sha = self.sha256.lower()
        if not _SHA256_RE.fullmatch(normalized_sha):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        object.__setattr__(self, "sha256", normalized_sha)
        _validate_dimensions(self.width, self.height)
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")
        if self.media_type == "image" and not self.mime_type.startswith("image/"):
            raise ValueError("image artifacts require an image/* MIME type")
