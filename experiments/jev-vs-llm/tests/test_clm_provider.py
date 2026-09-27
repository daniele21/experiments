from __future__ import annotations

from jev_bench.models import QuestionSpec
from jev_bench.providers.clm import CLMProvider


def test_clm_provider_replays_choice_wire_format_and_preserves_distribution():
    provider = CLMProvider(model="clm-latest", base_url="http://clm.test", temperature=1.0)
    captured = {}

    def fake_post(payload):
        captured.update(payload)
        return (
            {
                "model": "clm-latest",
                "answers": {
                    "intent": {
                        "type": "choice",
                        "choice": "billing",
                        "confidence": 0.91,
                        "probabilities": {"billing": 0.95, "technical": 0.05},
                    }
                },
                "usage": {"input_tokens": 38, "output_tokens": 0},
            },
            12.4,
        )

    provider._post = fake_post
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose one intent.",
        criteria={"billing": "Billing issue", "technical": "Technical issue"},
    )

    result = provider.evaluate("I was charged twice.", [question])

    assert captured["state"] == "I was charged twice."
    assert captured["questions"]["intent"] == {
        "type": "choice",
        "instructions": "Choose one intent.",
        "criteria": {"billing": "Billing issue", "technical": "Technical issue"},
    }
    assert result.valid is True
    assert result.provider == "clm"
    assert result.model == "clm-latest"
    assert result.answers["intent"].value == "billing"
    assert result.answers["intent"].probabilities == {
        "billing": 0.95,
        "technical": 0.05,
    }
    assert result.answers["intent"].predicted_probability == 0.95
    assert result.input_tokens == 38
    assert result.output_tokens == 0
    assert result.cached_input_tokens is None
    assert result.estimated_cost_usd == 0.0
    assert result.raw["server_latency_ms"] == 12.4


def test_clm_provider_maps_noul_to_existing_harness_semantics():
    provider = CLMProvider()
    provider._post = lambda payload: (
        {
            "model": "clm-latest",
            "answers": {"urgent": {"type": "noul", "noul": 0.8}},
            "usage": {},
        },
        None,
    )
    question = QuestionSpec(id="urgent", type="noul", instructions="Is this urgent?")

    result = provider.evaluate("Production is blocked.", [question])

    assert result.valid is True
    assert result.answers["urgent"].value == 0.8
    assert result.answers["urgent"].probabilities == {"yes": 0.8, "no": 0.2}
    assert result.answers["urgent"].confidence == 0.6000000000000001
    assert result.answers["urgent"].predicted_probability == 0.8


def test_clm_provider_fails_closed_on_missing_answer():
    provider = CLMProvider()
    provider._post = lambda payload: (
        {"model": "clm-latest", "answers": {}, "usage": {}},
        None,
    )
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose.",
        criteria={"a": "A", "b": "B"},
    )

    result = provider.evaluate("state", [question])

    assert result.valid is False
    assert result.answers == {}
    assert "answer ids mismatch" in (result.error or "")
