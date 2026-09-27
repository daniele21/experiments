from __future__ import annotations

import base64
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core import (
    ContentPart,
    InferenceError,
    InferenceRequest,
    InferenceResult,
    JsonHttpTransport,
    TokenUsage,
    inference_error_from_exception,
)
from cairosvg import svg2png


def _media_url(part: ContentPart) -> str:
    if part.media is None:
        raise ValueError("image content part is missing media")
    location = part.media.location
    if location.startswith(("http://", "https://", "data:")):
        return location

    path = Path(location)
    if not path.is_file():
        raise ValueError(f"image asset does not exist: {path}")
    raw = path.read_bytes()
    mime_type = part.media.mime_type
    if mime_type == "image/svg+xml" or path.suffix.lower() == ".svg":
        raw = svg2png(bytestring=raw)
        mime_type = "image/png"

    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _openai_content(request: InferenceRequest) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for part in request.content:
        if part.kind == "text":
            content.append({"type": "text", "text": part.text})
        elif part.kind == "image":
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _media_url(part)},
                }
            )
        else:
            raise ValueError(f"unsupported VLM content part: {part.kind}")

    if not content and isinstance(request.input, str) and request.input.strip():
        content.append({"type": "text", "text": request.input.strip()})
    if not content:
        raise ValueError("VLM request requires text and/or image content")
    return content


class OpenAICompatibleVLMProvider:
    provider_id = "openai-compatible-vlm"

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str,
        transport: JsonHttpTransport,
        api_key: str | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.api_key = api_key

    def generate(self, request: InferenceRequest) -> InferenceResult:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": _openai_content(request),
                }
            ],
        }
        if request.system_prompt:
            payload["messages"].insert(
                0,
                {"role": "system", "content": request.system_prompt},
            )
        if request.generation.max_output_tokens is not None:
            payload["max_tokens"] = request.generation.max_output_tokens
        if request.generation.temperature is not None:
            payload["temperature"] = request.generation.temperature

        provider_options = request.generation.extra.get("provider_options", {})
        if provider_options:
            if not isinstance(provider_options, Mapping):
                return self._invalid(
                    ValueError("provider_options must be a mapping"),
                    latency_ms=0.0,
                )
            reserved = {"model", "messages"}
            forbidden = reserved.intersection(provider_options)
            if forbidden:
                names = ", ".join(sorted(forbidden))
                return self._invalid(
                    ValueError(f"provider_options cannot override reserved fields: {names}"),
                    latency_ms=0.0,
                )
            payload.update(provider_options)

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        started = time.perf_counter()
        try:
            response = self.transport.request(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                payload=payload,
                headers=headers,
            )
            body = response.body
            choices = body.get("choices") if isinstance(body, dict) else None
            if not choices:
                raise ValueError("provider response is missing choices")
            message = choices[0].get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("provider response is missing textual content")

            usage = body.get("usage") or {}
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output=body,
                normalized_output=content,
                latency_ms=(time.perf_counter() - started) * 1000,
                usage=TokenUsage(
                    input_tokens=usage.get("prompt_tokens"),
                    cached_input_tokens=usage.get("cached_prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                ),
                metadata={"status_code": response.status_code},
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary captures failures
            return self._invalid(
                exc,
                latency_ms=(time.perf_counter() - started) * 1000,
            )

    def _invalid(self, exc: Exception, *, latency_ms: float) -> InferenceResult:
        error = inference_error_from_exception(exc)
        if error.kind == "unknown" and isinstance(exc, ValueError):
            error = InferenceError(
                kind="invalid_response",
                message=str(exc),
                retryable=False,
            )
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_output=None,
            latency_ms=latency_ms,
            valid=False,
            error=error,
        )
