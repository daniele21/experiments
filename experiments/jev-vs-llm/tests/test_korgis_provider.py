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
        assert kwargs["model"] == "qwen3.5-4b-q4km"
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
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(payload))
                )
            ],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


def test_default_korgis_matrix_is_quantized_local_comparison_set():
    assert DEFAULT_KORGIS_MODELS == [
        "qwen3.5-4b-q4km",
        "minicpm3-4b-q4km",
        "nemotron-nano-4b",
        "qwen3.5-9b-q4km",
    ]


def test_managed_order_runs_anchor_last():
    assert managed_korgis_model_order(
        [
            "nemotron-nano-4b",
            "qwen3.5-4b-q4km",
            "minicpm3-4b-q4km",
            "qwen3.5-9b-q4km",
        ],
        "nemotron-nano-4b",
    ) == [
        "qwen3.5-4b-q4km",
        "minicpm3-4b-q4km",
        "qwen3.5-9b-q4km",
        "nemotron-nano-4b",
    ]


def test_korgis_provider_parses_bounded_json_and_has_zero_provider_api_cost():
    provider = KorgisProvider("qwen3.5-4b-q4km")
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
    assert result.model == "qwen3.5-4b-q4km"
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
    provider = KorgisProvider("qwen3.5-4b-q4km")
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
