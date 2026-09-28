import json
from types import SimpleNamespace

from jev_bench.cli import (
    DEFAULT_OPENAI_MODELS,
    _local_model_matrix,
    _model_matrix,
)
from jev_bench.models import QuestionSpec
from jev_bench.providers.openai import OpenAIProvider
from jev_bench.providers.schema import decision_response_schema


def test_default_model_matrix_contains_three_gpt_tiers(monkeypatch):
    monkeypatch.delenv("OPENAI_MODELS", raising=False)
    assert _model_matrix() == DEFAULT_OPENAI_MODELS
    assert DEFAULT_OPENAI_MODELS == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
    ]


def test_model_matrix_deduplicates_preserving_order():
    assert _model_matrix("gpt-5.6-sol,gpt-5.6-luna,gpt-5.6-sol") == [
        "gpt-5.6-sol",
        "gpt-5.6-luna",
    ]


def test_local_matrix_can_be_overridden():
    assert _local_model_matrix("qwen3.5-4b-q4km,nemotron-nano-4b") == [
        "qwen3.5-4b-q4km",
        "nemotron-nano-4b",
    ]


def test_gpt_decision_provider_defaults_to_no_reasoning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)

    provider = OpenAIProvider("gpt-5.6-luna")

    assert provider.reasoning_effort == "none"


def test_decision_schema_binds_choice_to_question_id_and_allowed_values():
    questions = [
        QuestionSpec(
            id="intent",
            type="choice",
            instructions="Choose one intent.",
            criteria={"billing": "Billing", "support": "Support"},
        )
    ]

    schema = decision_response_schema(questions)

    answers = schema["properties"]["answers"]
    assert answers["minItems"] == answers["maxItems"] == 1
    answer = answers["items"]["anyOf"][0]
    assert answer["properties"]["id"]["const"] == "intent"
    assert answer["properties"]["value"]["enum"] == ["billing", "support"]


def test_openai_provider_sends_question_specific_choice_enum(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = OpenAIProvider("gpt-5.6-luna")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "answers": [
                        {
                            "id": "intent",
                            "value": "billing",
                            "confidence": 0.8,
                            "selected_probability": 0.75,
                        }
                    ]
                }
            ),
            usage=None,
        )

    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose one intent.",
        criteria={"billing": "Billing", "support": "Support"},
    )

    result = provider.evaluate("I was charged twice.", [question])

    answer = captured["text"]["format"]["schema"]["properties"]["answers"][
        "items"
    ]["anyOf"][0]
    assert answer["properties"]["value"]["enum"] == ["billing", "support"]
    assert result.valid is True
