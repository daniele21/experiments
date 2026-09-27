from __future__ import annotations

from pathlib import Path

from benchmark_core import (
    ContentPart,
    GenerationConfig,
    InferenceProvider,
    InferenceRequest,
    JsonHttpResponse,
    MediaRef,
    TransportError,
    sha256_file,
)

from vlm_bench.providers import OpenAICompatibleVLMProvider


class FakeTransport:
    def __init__(self, response: JsonHttpResponse | Exception) -> None:
        self.response = response
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
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _image_part(path: Path) -> ContentPart:
    return ContentPart(
        kind="image",
        media=MediaRef(
            media_id="ui-1",
            media_type="image",
            location=str(path),
            mime_type="image/png",
            sha256=sha256_file(path),
        ),
    )


def test_openai_compatible_vlm_builds_multimodal_chat_request(tmp_path) -> None:
    image = tmp_path / "screen.png"
    image.write_bytes(b"fake-png")
    transport = FakeTransport(
        JsonHttpResponse(
            body={
                "choices": [{"message": {"content": '{"x": 0.8, "y": 0.12}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
            headers={},
            status_code=200,
        )
    )
    provider = OpenAICompatibleVLMProvider(
        model_id="Qwen/Qwen3-VL-4B-Instruct",
        base_url="http://localhost:8000",
        transport=transport,
    )
    request = InferenceRequest(
        request_id="ui-1",
        content=(
            ContentPart(kind="text", text="Where should I click?"),
            _image_part(image),
        ),
    )

    result = provider.generate(request)

    assert isinstance(provider, InferenceProvider)
    assert result.valid
    assert result.normalized_output == '{"x": 0.8, "y": 0.12}'
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 20
    call = transport.calls[0]
    assert call["url"] == "http://localhost:8000/v1/chat/completions"
    assert call["payload"]["model"] == "Qwen/Qwen3-VL-4B-Instruct"
    content = call["payload"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Where should I click?"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_vlm_provider_maps_transport_failures() -> None:
    transport = FakeTransport(
        TransportError(
            kind="timeout",
            message="timed out",
            retryable=True,
        )
    )
    provider = OpenAICompatibleVLMProvider(
        model_id="vlm-test",
        base_url="http://localhost:8000",
        transport=transport,
    )

    result = provider.generate(InferenceRequest(request_id="text-1", input="Hello"))

    assert not result.valid
    assert result.error is not None
    assert result.error.kind == "timeout"
    assert result.error.retryable


def test_vlm_provider_rejects_reserved_overrides() -> None:
    transport = FakeTransport(
        JsonHttpResponse(
            body={"choices": [{"message": {"content": "unused"}}]},
            headers={},
            status_code=200,
        )
    )
    provider = OpenAICompatibleVLMProvider(
        model_id="vlm-test",
        base_url="http://localhost:8000",
        transport=transport,
    )
    request = InferenceRequest(
        request_id="bad-overrides",
        input="Hello",
        generation=GenerationConfig(
            extra={"provider_options": {"model": "different-model"}}
        ),
    )

    result = provider.generate(request)

    assert not result.valid
    assert result.error is not None
    assert result.error.kind == "invalid_response"
    assert not transport.calls
