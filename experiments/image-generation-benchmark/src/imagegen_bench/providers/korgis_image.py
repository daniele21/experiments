from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from benchmark_core import ArtifactStore, InferenceRequest, InferenceResult, JsonHttpTransport

from imagegen_bench.providers.common import (
    decode_base64_image,
    extract_prompt,
    invalid_result,
    mime_type_for_output_format,
)


class KorgisImageProvider:
    provider_id = "korgis-image"

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str,
        transport: JsonHttpTransport,
        artifact_store: ArtifactStore,
        generation_options: Mapping[str, Any],
        api_key: str | None = None,
    ) -> None:
        if not model_id.strip():
            raise ValueError("model_id must not be empty")
        if not base_url.strip():
            raise ValueError("base_url must not be empty")
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.artifact_store = artifact_store
        self.generation_options = dict(generation_options)
        self.api_key = api_key

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            prompt = extract_prompt(request)
            options = dict(self.generation_options)
            overrides = request.generation.extra.get("provider_options", {})
            if overrides:
                if not isinstance(overrides, Mapping):
                    raise ValueError("provider_options must be a mapping")
                options.update(overrides)

            output_format = str(options.get("output_format") or "png")
            payload: dict[str, Any] = {
                "model": self.model_id,
                "prompt": prompt,
                "n": 1,
                "response_format": "b64_json",
                **options,
            }
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = self.transport.request(
                "POST",
                f"{self.base_url}/v1/images/generations",
                payload=payload,
                headers=headers,
            )
            body = response.body
            if not isinstance(body, Mapping):
                raise ValueError("Korgis image provider returned a non-object response")
            data = body.get("data")
            if not isinstance(data, list) or not data:
                raise ValueError("Korgis image provider returned no image data")
            first = data[0]
            if not isinstance(first, Mapping):
                raise ValueError("Korgis image provider returned invalid image data")
            image_bytes = decode_base64_image(str(first.get("b64_json") or ""))

            korgis_metadata = body.get("korgis")
            if not isinstance(korgis_metadata, Mapping):
                korgis_metadata = {}
            mime_type = str(
                korgis_metadata.get("mime_type")
                or mime_type_for_output_format(output_format)
            )
            artifact = self.artifact_store.persist_bytes(
                artifact_id=f"{request.request_id}-{self.provider_id}-0",
                media_type="image",
                data=image_bytes,
                mime_type=mime_type,
                width=(
                    int(korgis_metadata["width"])
                    if korgis_metadata.get("width") is not None
                    else None
                ),
                height=(
                    int(korgis_metadata["height"])
                    if korgis_metadata.get("height") is not None
                    else None
                ),
                metadata={
                    "provider_id": self.provider_id,
                    "model_id": self.model_id,
                    "request_id": request.request_id,
                },
            )
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output={
                    "created": body.get("created"),
                    "korgis": dict(korgis_metadata),
                },
                normalized_output={"artifact_id": artifact.artifact_id},
                output_artifacts=(artifact,),
                latency_ms=(time.perf_counter() - started) * 1000,
                metadata={
                    "generation_options": options,
                    "korgis": dict(korgis_metadata),
                },
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary captures failures
            return invalid_result(
                provider_id=self.provider_id,
                model_id=self.model_id,
                latency_ms=(time.perf_counter() - started) * 1000,
                exc=exc,
                metadata={"generation_options": dict(self.generation_options)},
            )
