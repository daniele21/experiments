from __future__ import annotations

import json
from types import SimpleNamespace

from jev_bench.models import QuestionSpec
from jev_bench.providers.korgis import (
    DEFAULT_KORGIS_MODELS,
    KorgisProvider,
    managed_korgis_model_order,
)


class _FakeChatCompletions:
    def create(self, **kwargs):
        assert kwargs["model"] == "nemotron-nano-4b"
        assert kwargs["extra_body"]["enable_thinking"] is False
        assert kwargs["response_format"] == {"type": "json_object"}
        user_payload = json.loads(kwargs["messages"][1]["content"])
        assert user_payload["required_answer_ids"] == ["intent"]
        assert "output_example" not in user_payload
        assert "question_id" not in kwargs["messages"][1]["content"]
        payload = {
            "answers": [
                {
                    "id": "intent",
                    "value": "billing",
                    "confidence": 0.8,
                    "selected_probability": 0.75,
                }
            ]
        }
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


def test_default_korgis_matrix_contains_only_built_in_registry_models():
    assert DEFAULT_KORGIS_MODELS == [
        "nemotron-nano-4b-q4",
        "qwen3-vl-4b",
    ]


def test_managed_order_runs_anchor_last():
    assert managed_korgis_model_order(
        [
            "nemotron-nano-4b-q4",
            "qwen3-vl-4b",
        ],
        "nemotron-nano-4b-q4",
    ) == [
        "qwen3-vl-4b",
        "nemotron-nano-4b-q4",
    ]


def test_korgis_provider_parses_bounded_json_and_has_zero_provider_api_cost():
    provider = KorgisProvider("nemotron-nano-4b")
    provider.client = _FakeClient()
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose one intent.",
        criteria={"billing": "Billing", "support": "Support"},
    )

    result = provider.evaluate("I was charged twice.", [question])

    assert result.valid is True
    assert result.provider == "local-korgis"
    assert result.model == "nemotron-nano-4b"
    assert result.answers["intent"].value == "billing"
    assert result.answers["intent"].predicted_probability == 0.75
    assert result.input_tokens == 120
    assert result.output_tokens == 30
    assert result.estimated_cost_usd == 0.0


class _FakeBooleanNoulChatCompletions:
    def create(self, **kwargs):
        payload = {
            "answers": [
                {
                    "id": "urgent",
                    "value": False,
                    "confidence": "0.7",
                    "selected_probability": 0.7,
                }
            ]
        }
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
            usage=SimpleNamespace(prompt_tokens=80, completion_tokens=20),
        )


class _FakeBooleanNoulClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeBooleanNoulChatCompletions())


def test_korgis_provider_accepts_boolean_noul_as_bounded_probability():
    provider = KorgisProvider("nemotron-nano-4b")
    provider.client = _FakeBooleanNoulClient()
    question = QuestionSpec(
        id="urgent",
        type="noul",
        instructions="Is this urgent?",
    )

    result = provider.evaluate("No hurry.", [question])

    assert result.valid is True
    assert result.answers["urgent"].value == 0.0
    assert result.answers["urgent"].predicted_probability == 1.0
    assert result.answers["urgent"].confidence == 0.7


def _thinking_response(content, finish_reason):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning_content="Reasoning"),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1514, completion_tokens=4096),
    )


def test_thinking_limit_preserves_usage_and_raw_response():
    provider = KorgisProvider("qwen", enable_thinking=True, max_tokens=4096)
    response = _thinking_response("", "length")
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response))
    )
    result = provider.evaluate("public input", [])
    assert result.valid is False
    assert "generation_limit_reached" in result.error
    assert "final_content_chars=0" in result.error
    assert result.output_tokens == 4096
    assert result.input_tokens == 1514
    assert result.raw is response


def test_empty_final_is_distinct_from_malformed_json():
    provider = KorgisProvider("qwen", enable_thinking=True)
    for content, error in [("", "empty_final_content"), ("not JSON", "JSONDecodeError")]:
        response = _thinking_response(content, "stop")
        provider.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response))
        )
        result = provider.evaluate("public input", [])
        assert error in result.error
        assert result.raw is response
        assert result.output_tokens == 4096


def test_explicit_sampling_and_budget_reach_thinking_request(monkeypatch):
    monkeypatch.setenv("KORGIS_MAX_OUTPUT_TOKENS", "512")
    provider = KorgisProvider(
        "qwen", enable_thinking=True, max_tokens=8192, sampling={"temperature": 1.0, "top_k": 20}
    )
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return _thinking_response('{"answers": []}', "stop")

    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    result = provider.evaluate("public input", [])
    assert result.valid
    assert captured["max_tokens"] == 8192
    assert captured["response_format"] is None
    assert captured["extra_body"] == dict(
        enable_thinking=True, show_thinking=False, temperature=1.0, top_k=20
    )
