from __future__ import annotations

import base64

from benchmark_core import ArtifactStore, InferenceRequest, JsonHttpResponse

from imagegen_bench.providers import KorgisImageProvider


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, url, *, payload=None, headers=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "payload": payload,
                "headers": dict(headers or {}),
            }
        )
        return JsonHttpResponse(
            body={
                "created": 1,
                "model": "Qwen/Qwen-Image-2.1",
                "data": [
                    {
                        "b64_json": base64.b64encode(
                            b"korgis-qwen-image"
                        ).decode("ascii")
                    }
                ],
                "korgis": {
                    "runtime_key": "qwen-image-2.1",
                    "backend": "diffusers_image",
                    "mime_type": "image/png",
                    "width": 1024,
                    "height": 1024,
                    "seed": 42,
                    "latency_ms": 123.0,
                },
            },
            headers={},
            status_code=200,
        )


def test_korgis_image_provider_persists_local_output_and_provenance(tmp_path) -> None:
    transport = FakeTransport()
    provider = KorgisImageProvider(
        model_id="qwen-image-2.1",
        base_url="http://127.0.0.1:1235",
        transport=transport,
        artifact_store=ArtifactStore(tmp_path),
        generation_options={
            "output_format": "png",
            "size": "1024x1024",
            "num_inference_steps": 40,
        },
    )

    result = provider.generate(
        InferenceRequest(request_id="prompt-1", input="A red cube")
    )

    assert result.valid
    assert result.provider_id == "korgis-image"
    assert result.model_id == "qwen-image-2.1"
    assert len(result.output_artifacts) == 1
    artifact = result.output_artifacts[0]
    assert artifact.mime_type == "image/png"
    assert artifact.width == 1024
    assert artifact.height == 1024
    assert artifact.size_bytes == len(b"korgis-qwen-image")
    assert result.metadata["korgis"]["runtime_key"] == "qwen-image-2.1"
    assert result.metadata["korgis"]["backend"] == "diffusers_image"

    [call] = transport.calls
    assert call["url"] == "http://127.0.0.1:1235/v1/images/generations"
    assert call["payload"] == {
        "model": "qwen-image-2.1",
        "prompt": "A red cube",
        "n": 1,
        "response_format": "b64_json",
        "output_format": "png",
        "size": "1024x1024",
        "num_inference_steps": 40,
    }


def test_korgis_image_provider_forwards_optional_local_auth(tmp_path) -> None:
    transport = FakeTransport()
    provider = KorgisImageProvider(
        model_id="qwen-image-2.1",
        base_url="http://127.0.0.1:1235",
        transport=transport,
        artifact_store=ArtifactStore(tmp_path),
        generation_options={"output_format": "png"},
        api_key="local-token",
    )

    result = provider.generate(
        InferenceRequest(request_id="prompt-2", input="A blue sphere")
    )

    assert result.valid
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer local-token"
