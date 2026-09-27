from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from benchmark_core import ArtifactStore, InferenceRequest, InferenceResult

from imagegen_bench.providers.common import (
    decode_base64_image,
    extract_prompt,
    invalid_result,
    mime_type_for_output_format,
)


class OpenAIImageProvider:
    provider_id = "openai-image"

    def __init__(
        self,
        *,
        model_id: str,
        client: Any,
        artifact_store: ArtifactStore,
        generation_options: Mapping[str, Any],
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        if "output_format" not in generation_options:
            raise ValueError("OpenAI image generation requires explicit output_format")
        self.model_id = model_id
        self.client = client
        self.artifact_store = artifact_store
        self.generation_options = dict(generation_options)

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            prompt = extract_prompt(request)
            options = dict(self.generation_options)
            request_overrides = request.generation.extra.get("provider_options", {})
            if request_overrides:
                if not isinstance(request_overrides, Mapping):
                    raise ValueError("provider_options must be a mapping")
                options.update(request_overrides)

            result = self.client.images.generate(
                model=self.model_id,
                prompt=prompt,
                **options,
            )
            if not getattr(result, "data", None):
                raise ValueError("OpenAI image provider returned no image data")
            encoded = getattr(result.data[0], "b64_json", None)
            image_bytes = decode_base64_image(encoded)
            output_format = str(options["output_format"])
            artifact = self.artifact_store.persist_bytes(
                artifact_id=f"{request.request_id}-{self.provider_id}-0",
                media_type="image",
                data=image_bytes,
                mime_type=mime_type_for_output_format(output_format),
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
                    "image_count": len(result.data),
                    "provider_response_id": getattr(result, "id", None),
                },
                normalized_output={"artifact_id": artifact.artifact_id},
                output_artifacts=(artifact,),
                latency_ms=latency_ms,
                metadata={"generation_options": options},
            )
        except Exception as exc:
            return invalid_result(
                provider_id=self.provider_id,
                model_id=self.model_id,
                latency_ms=(time.perf_counter() - started) * 1000,
                exc=exc,
                metadata={"generation_options": dict(self.generation_options)},
            )


def create_openai_image_client(*, api_key: str, policy: Any) -> Any:
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        max_retries=policy.max_retries,
        timeout=policy.timeout_seconds,
    )
