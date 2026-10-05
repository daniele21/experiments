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


def test_openai_responses_provider_omits_temperature_and_adapts_optional_schema() -> None:
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
        "properties": {
            "name": {"type": "string"},
            "manager": {"type": "string"},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    result = provider.generate(
        InferenceRequest(
            request_id="req-opt",
            input={"question": "Employee info"},
            system_prompt="Return json.",
            response_schema=schema,
            generation=InferenceRequest(
                request_id="sub",
                input={},
            ).generation,
        )
    )

    client = _FakeOpenAI.instances[-1]
    call = client.response_calls[0]
    assert "temperature" not in call
    assert call["text"]["format"]["strict"] is False
    assert call["text"]["format"]["schema"] == schema
    assert result.valid is True


def test_typesafe_jev_provider_builds_and_evaluates(monkeypatch) -> None:
    from model_capability_bench.providers.typesafe_json import TypeSafeJevJsonProvider

    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("jev-1.13.0")
    provider = build_inference_provider(
        model,
        {
            "TYPESAFE_API_KEY": "test-key",
            "BENCHMARK_MAX_RETRIES": "0",
            "BENCHMARK_TIMEOUT_SECONDS": "20",
        },
    )
    assert isinstance(provider, TypeSafeJevJsonProvider)

    class _MockAnswer:
        choice = "card_arrival"
        confidence = 0.98

    class _MockResponse:
        def __init__(self):
            self.answers = {"intent": _MockAnswer()}
            self.usage = type("Usage", (), {"input_tokens": 120, "output_tokens": 15})()
            self.model = "jev-1.13.0"

        def model_dump(self):
            return {"status": "ok"}

    monkeypatch.setattr(provider.client, "system_one", lambda **kwargs: _MockResponse())

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["card_arrival", "pin_change"]},
            "confidence": {"type": "number"},
        },
        "required": ["intent", "confidence"],
    }
    result = provider.generate(
        InferenceRequest(
            request_id="req-jev",
            input={"text": "When will my card arrive?"},
            system_prompt="Classify intent",
            response_schema=schema,
        )
    )
    assert result.valid is True
    assert result.normalized_output == {"intent": "card_arrival", "confidence": 0.98}
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 15


def test_decisio_provider_builds_and_evaluates(monkeypatch) -> None:
    import json
    from io import StringIO

    from model_capability_bench.providers.decisio_json import DecisioJsonProvider

    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("decisio-qwen3.5-2b-q4km")

    class _MockProc:
        def __init__(self):
            self.stdin = StringIO()
            self.stdout = StringIO(
                json.dumps({"status": "ready"})
                + "\n"
                + json.dumps(
                    {
                        "request_id": "req-decisio",
                        "choice": "card_arrival",
                        "valid": True,
                        "generated_tokens": 6,
                        "latency_ms": 150.0,
                    }
                )
                + "\n"
            )
            self.stderr = StringIO()

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: _MockProc())

    provider = build_inference_provider(
        model,
        {"DECISIO_MODEL_PATH": "/path/to/fake.gguf"},
    )
    assert isinstance(provider, DecisioJsonProvider)

    schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["card_arrival", "pin_change"]},
            "confidence": {"type": "number"},
        },
        "required": ["intent", "confidence"],
    }
    result = provider.generate(
        InferenceRequest(
            request_id="req-decisio",
            input={"text": "When will my card arrive?"},
            system_prompt="Classify intent",
            response_schema=schema,
        )
    )
    assert result.valid is True
    assert result.normalized_output == {"intent": "card_arrival", "confidence": 0.90}
    assert result.usage.output_tokens == 6
    assert result.estimated_cost_usd == 0.0



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
        return {
            "ok": True,
            "key": model_key,
            "runtime_identity": {
                "fingerprint": "a" * 64,
                "captured_at": 1.0,
                "identity": {
                    "schema_version": 1,
                    "artifact_key": "b" * 64,
                    "backend": {
                        "name": "llama_server",
                        "version": "build-10709@prism123",
                        "implementation": "LlamaServerEngine",
                    },
                    "config_digest": "c" * 64,
                    "hardware_key": "d" * 64,
                },
            },
            "cfg": {
                "backend": "llama_server",
                "quantization": "PTQ1_0",
            },
        }

    def resources(self):
        self.calls.append(("resources", None))
        return {
            "observation": {
                "captured_at_utc": "2026-10-05T08:00:00+00:00",
                "captured_at_monotonic": 1.0,
                "system": {},
                "runtimes": [],
            }
        }

    def unload(self, model_key: str):
        self.calls.append(("unload", model_key))
        return {"ok": True}


def test_korgis_resource_telemetry_can_be_disabled() -> None:
    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("qwen3.5-2b-q4km")

    runtime = KorgisManagedRuntime(
        environ={
            "KORGIS_BASE_URL": "http://127.0.0.1:1235/v1",
            "MCB_RESOURCE_TELEMETRY": "off",
        },
        provider_builder=lambda _resolved, _environ: _FakeProvider(),
        control_factory=_FakeControl,
    )

    provider = runtime.prepare(model)

    assert isinstance(provider, _FakeProvider)


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
    execution_metadata = runtime.execution_metadata(model)
    runtime.release(model)

    assert isinstance(provider.delegate, _FakeProvider)
    assert execution_metadata["runtime_source"] == "korgis"
    assert execution_metadata["runtime_identity"]["fingerprint"] == "a" * 64
    assert (
        execution_metadata["runtime_identity"]["identity"]["backend"]["version"]
        == "build-10709@prism123"
    )
    assert execution_metadata["backend"] == "llama_server"
    assert execution_metadata["quantization"] == "PTQ1_0"
    assert built == ["qwen3.5-2b-q4km"]
    control = _FakeControl.instances[-1]
    assert control.timeout_seconds == 9.0
    assert control.calls == [
        ("health", None),
        ("activate", "qwen3.5-2b-q4km"),
        ("unload", "qwen3.5-2b-q4km"),
    ]
