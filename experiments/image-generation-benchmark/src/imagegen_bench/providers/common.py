from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from benchmark_core import InferenceError, InferenceRequest, InferenceResult


def extract_prompt(request: InferenceRequest) -> str:
    if isinstance(request.input, str) and request.input.strip():
        return request.input.strip()

    text_parts = [
        part.text.strip()
        for part in request.content
        if part.kind == "text" and part.text is not None and part.text.strip()
    ]
    if text_parts:
        return "\n".join(text_parts)

    raise ValueError("image generation request requires a non-empty text prompt")


def decode_base64_image(value: str) -> bytes:
    if not value:
        raise ValueError("provider returned empty image data")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("provider returned invalid base64 image data") from exc


def mime_type_for_output_format(output_format: str) -> str:
    normalized = output_format.strip().lower()
    mapping = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "webp": "image/webp",
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported image output format: {output_format}") from exc


def invalid_result(
    *,
    provider_id: str,
    model_id: str,
    latency_ms: float,
    exc: Exception,
    metadata: Mapping[str, Any] | None = None,
) -> InferenceResult:
    return InferenceResult(
        provider_id=provider_id,
        model_id=model_id,
        raw_output=None,
        latency_ms=max(latency_ms, 0.0),
        valid=False,
        error=InferenceError(
            kind="provider",
            message=f"{type(exc).__name__}: {exc}",
            retryable=False,
        ),
        metadata=dict(metadata or {}),
    )
