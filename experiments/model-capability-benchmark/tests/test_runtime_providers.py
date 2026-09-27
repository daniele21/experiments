from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest
from benchmark_core import InferenceRequest

from model_capability_bench import load_capability_suite
from model_capability_bench.providers import build_inference_provider
from model_capability_bench.runtimes import KorgisManagedRuntime

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class _FakeOpenAI:
    instances: ClassVar[list[_FakeOpenAI]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat_calls: list[dict] = []
        self.response_calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._chat_create)
        )
        self.responses = SimpleNamespace(create=self._responses_create)
        self.__class__.instances.append(self)

    def _chat_create(self, **kwargs):
        self.chat_calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"label":"fixture"}')
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=4),
            model_dump=lambda: {"kind": "chat"},
        )

    def _responses_create(self, **kwargs):
        self.response_calls.append(kwargs)
        return SimpleNamespace(
            output_text='{"answer":"42"}',
            usage=SimpleNamespace(
                input_tokens=12,
                output_tokens=5,
                input_tokens_details=SimpleNamespace(cached_tokens=3),
            ),
            model_dump=lambda: {"kind": "responses"},
        )


@pytest.fixture(autouse=True)
def _reset_fake_openai(monkeypatch):
    from model_capability_bench.providers import openai_json

    _FakeOpenAI.instances.clear()
    monkeypatch.setattr(openai_json, "OpenAI", _FakeOpenAI)


def test_openai_compatible_provider_uses_registry_runtime_model_and_local_cost() -> None:
    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("qwen3.5-2b-q4km")
    provider = build_inference_provider(
        model,
        {
            "KORGIS_BASE_URL": "http://korgis.test/v1",
            "BENCHMARK_MAX_RETRIES": "1",
            "BENCHMARK_TIMEOUT_SECONDS": "15",
        },
    )

    result = provider.generate(
        InferenceRequest(
            request_id="req-1",
            input="hello",
            response_schema={
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"],
            },
        )
    )

    client = _FakeOpenAI.instances[-1]
    assert client.kwargs == {
        "max_retries": 1,
        "timeout": 15.0,
        "base_url": "http://korgis.test/v1",
        "api_key": "local",
    }
    assert client.chat_calls[0]["model"] == "qwen3.5-2b-q4km"
    assert result.normalized_output == {"label": "fixture"}
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 4
    assert result.estimated_cost_usd == 0.0


def test_openai_responses_provider_uses_strict_schema_and_unknown_cost() -> None:
    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("gpt-5.6-luna")
    provider = build_inference_provider(
        model,
        {
            "OPENAI_API_KEY": "test-key",
            "BENCHMARK_MAX_RETRIES": "0",
            "BENCHMARK_TIMEOUT_SECONDS": "20",
        },
    )
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    result = provider.generate(
        InferenceRequest(
            request_id="req-2",
            input={"question": "6 * 7"},
            system_prompt="Return the answer.",
            response_schema=schema,
        )
    )

    client = _FakeOpenAI.instances[-1]
    call = client.response_calls[0]
    assert call["model"] == "gpt-5.6-luna"
    assert call["instructions"] == "Return the answer."
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"] == schema
    assert result.normalized_output == {"answer": "42"}
    assert result.usage.cached_input_tokens == 3
    assert result.estimated_cost_usd is None


class _FakeProvider:
    provider_id = "fake"

    def generate(self, request):
        raise AssertionError("not used")


class _FakeControl:
    instances: ClassVar[list[_FakeControl]] = []

    def __init__(self, *, base_url: str, timeout_seconds: float):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.calls: list[tuple[str, str | None]] = []
        self.__class__.instances.append(self)

    def health(self):
        self.calls.append(("health", None))
        return {"ok": True}

    def activate(self, model_key: str):
        self.calls.append(("activate", model_key))
        return {"ok": True}

    def unload(self, model_key: str):
        self.calls.append(("unload", model_key))
        return {"ok": True}


def test_korgis_runtime_manages_model_residency_without_server_process_logic() -> None:
    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("qwen3.5-2b-q4km")
    built: list[str] = []

    def provider_builder(resolved, environ):
        built.append(resolved.model.model_key)
        return _FakeProvider()

    runtime = KorgisManagedRuntime(
        environ={
            "KORGIS_BASE_URL": "http://127.0.0.1:1235/v1",
            "KORGIS_CONTROL_TIMEOUT_SECONDS": "9",
        },
        provider_builder=provider_builder,
        control_factory=_FakeControl,
    )

    provider = runtime.prepare(model)
    runtime.release(model)

    assert isinstance(provider, _FakeProvider)
    assert built == ["qwen3.5-2b-q4km"]
    control = _FakeControl.instances[-1]
    assert control.timeout_seconds == 9.0
    assert control.calls == [
        ("health", None),
        ("activate", "qwen3.5-2b-q4km"),
        ("unload", "qwen3.5-2b-q4km"),
    ]
