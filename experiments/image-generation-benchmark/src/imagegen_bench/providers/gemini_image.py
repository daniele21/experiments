from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from benchmark_core import ArtifactStore, InferenceRequest, InferenceResult

from imagegen_bench.providers.common import decode_base64_image, extract_prompt, invalid_result


class GeminiImageProvider:
    provider_id = "gemini-image"

    def __init__(
        self,
        *,
        model_id: str,
        client: Any,
        artifact_store: ArtifactStore,
        response_format: Mapping[str, Any],
        generation_config: Mapping[str, Any] | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        if response_format.get("type") != "image":
            raise ValueError("Gemini image response_format.type must be image")
        mime_type = response_format.get("mime_type")
        if not isinstance(mime_type, str) or not mime_type.startswith("image/"):
            raise ValueError("Gemini image response_format requires explicit image MIME type")
        self.model_id = model_id
        self.client = client
        self.artifact_store = artifact_store
        self.response_format = dict(response_format)
        self.generation_config = dict(generation_config or {})

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            prompt = extract_prompt(request)
            response_format = dict(self.response_format)
            generation_config = dict(self.generation_config)

            overrides = request.generation.extra.get("provider_options", {})
            if overrides:
                if not isinstance(overrides, Mapping):
                    raise ValueError("provider_options must be a mapping")
                format_override = overrides.get("response_format")
                generation_override = overrides.get("generation_config")
                if format_override:
                    if not isinstance(format_override, Mapping):
                        raise ValueError("response_format override must be a mapping")
                    response_format.update(format_override)
                if generation_override:
                    if not isinstance(generation_override, Mapping):
                        raise ValueError("generation_config override must be a mapping")
                    generation_config.update(generation_override)

            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "input": prompt,
                "response_format": response_format,
            }
            if generation_config:
                kwargs["generation_config"] = generation_config

            interaction = self.client.interactions.create(**kwargs)
            output_image = getattr(interaction, "output_image", None)
            encoded = getattr(output_image, "data", None)
            image_bytes = decode_base64_image(encoded)
            artifact = self.artifact_store.persist_bytes(
                artifact_id=f"{request.request_id}-{self.provider_id}-0",
                media_type="image",
                data=image_bytes,
                mime_type=str(response_format["mime_type"]),
                metadata={
                    "provider_id": self.provider_id,
                    "model_id": self.model_id,
                    "request_id": request.request_id,
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output={
                    "provider_response_id": getattr(interaction, "id", None),
                    "output_text": getattr(interaction, "output_text", None),
                },
                normalized_output={"artifact_id": artifact.artifact_id},
                output_artifacts=(artifact,),
                latency_ms=latency_ms,
                metadata={
                    "response_format": response_format,
                    "generation_config": generation_config,
                },
            )
        except Exception as exc:
            return invalid_result(
                provider_id=self.provider_id,
                model_id=self.model_id,
                latency_ms=(time.perf_counter() - started) * 1000,
                exc=exc,
                metadata={
                    "response_format": dict(self.response_format),
                    "generation_config": dict(self.generation_config),
                },
            )


def create_gemini_image_client(*, api_key: str) -> Any:
    from google import genai

    return genai.Client(api_key=api_key)
