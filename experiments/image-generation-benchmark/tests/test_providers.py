from __future__ import annotations

import base64
from types import SimpleNamespace

from benchmark_core import ArtifactStore, InferenceProvider, InferenceRequest

from imagegen_bench.providers import GeminiImageProvider, OpenAIImageProvider


class FakeOpenAIImages:
    def __init__(self) -> None:
        self.last_kwargs = None

    def generate(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            id="openai-response-1",
            data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(b"openai-image-bytes").decode("ascii")
                )
            ],
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.images = FakeOpenAIImages()


class FakeGeminiInteractions:
    def __init__(self) -> None:
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            id="gemini-interaction-1",
            output_text=None,
            output_image=SimpleNamespace(
                data=base64.b64encode(b"gemini-image-bytes").decode("ascii")
            ),
        )


class FakeGeminiClient:
    def __init__(self) -> None:
        self.interactions = FakeGeminiInteractions()


def test_openai_image_provider_persists_artifact_and_forwards_config(tmp_path) -> None:
    client = FakeOpenAIClient()
    provider = OpenAIImageProvider(
        model_id="gpt-image-test",
        client=client,
        artifact_store=ArtifactStore(tmp_path),
        generation_options={
            "output_format": "png",
            "size": "1024x1024",
            "quality": "high",
        },
    )

    result = provider.generate(InferenceRequest(request_id="prompt-1", input="Draw a cube"))

    assert isinstance(provider, InferenceProvider)
    assert result.valid
    assert result.model_id == "gpt-image-test"
    assert len(result.output_artifacts) == 1
    assert result.output_artifacts[0].mime_type == "image/png"
    assert result.output_artifacts[0].size_bytes == len(b"openai-image-bytes")
    assert client.images.last_kwargs == {
        "model": "gpt-image-test",
        "prompt": "Draw a cube",
        "output_format": "png",
        "size": "1024x1024",
        "quality": "high",
    }


def test_gemini_image_provider_persists_artifact_and_forwards_config(tmp_path) -> None:
    client = FakeGeminiClient()
    provider = GeminiImageProvider(
        model_id="gemini-image-test",
        client=client,
        artifact_store=ArtifactStore(tmp_path),
        response_format={
            "type": "image",
            "mime_type": "image/png",
            "aspect_ratio": "1:1",
            "image_size": "1K",
        },
    )

    result = provider.generate(InferenceRequest(request_id="prompt-2", input="Draw a sphere"))

    assert isinstance(provider, InferenceProvider)
    assert result.valid
    assert result.model_id == "gemini-image-test"
    assert len(result.output_artifacts) == 1
    assert result.output_artifacts[0].mime_type == "image/png"
    assert result.output_artifacts[0].size_bytes == len(b"gemini-image-bytes")
    assert client.interactions.last_kwargs == {
        "model": "gemini-image-test",
        "input": "Draw a sphere",
        "response_format": {
            "type": "image",
            "mime_type": "image/png",
            "aspect_ratio": "1:1",
            "image_size": "1K",
        },
    }


def test_provider_overrides_are_request_scoped(tmp_path) -> None:
    client = FakeOpenAIClient()
    provider = OpenAIImageProvider(
        model_id="gpt-image-test",
        client=client,
        artifact_store=ArtifactStore(tmp_path),
        generation_options={
            "output_format": "png",
            "size": "1024x1024",
            "quality": "high",
        },
    )
    request = InferenceRequest(
        request_id="prompt-3",
        input="Draw a triangle",
    )
    request = InferenceRequest(
        request_id=request.request_id,
        input=request.input,
        generation=request.generation.__class__(
            extra={"provider_options": {"quality": "xhigh"}}
        ),
    )

    result = provider.generate(request)

    assert result.valid
    assert client.images.last_kwargs["quality"] == "xhigh"
    assert provider.generation_options["quality"] == "high"


def test_invalid_provider_payload_is_recorded_as_failure(tmp_path) -> None:
    client = FakeOpenAIClient()
    client.images.generate = lambda **_: SimpleNamespace(data=[])
    provider = OpenAIImageProvider(
        model_id="gpt-image-test",
        client=client,
        artifact_store=ArtifactStore(tmp_path),
        generation_options={"output_format": "png"},
    )

    result = provider.generate(InferenceRequest(request_id="bad-1", input="Draw"))

    assert not result.valid
    assert result.error is not None
    assert result.error.kind == "provider"
    assert "no image data" in result.error.message
