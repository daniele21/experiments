from __future__ import annotations

import pytest
from benchmark_core.transports import JsonHttpResponse, TransportPolicy

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
    assert result.answers["urgent"].probabilities["yes"] == pytest.approx(0.8)
    assert result.answers["urgent"].probabilities["no"] == pytest.approx(0.2)
    assert result.answers["urgent"].confidence == pytest.approx(0.6)
    assert result.answers["urgent"].predicted_probability == 0.8


def test_clm_provider_accepts_banking77_sized_choice_space():
    provider = CLMProvider()
    criteria = {f"intent_{index}": f"Banking intent {index}" for index in range(77)}
    probabilities = {key: 0.2 / 76 for key in criteria}
    probabilities["intent_42"] = 0.8

    def fake_post(payload):
        assert len(payload["questions"]["intent"]["criteria"]) == 77
        return (
            {
                "model": "clm-latest",
                "answers": {
                    "intent": {
                        "type": "choice",
                        "choice": "intent_42",
                        "confidence": 0.79,
                        "probabilities": probabilities,
                    }
                },
                "usage": {},
            },
            None,
        )

    provider._post = fake_post
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Classify the banking request.",
        criteria=criteria,
    )

    result = provider.evaluate("Where is my transfer?", [question])

    assert result.valid is True
    assert len(result.answers["intent"].probabilities) == 77
    assert result.answers["intent"].value == "intent_42"
    assert result.answers["intent"].predicted_probability == pytest.approx(0.8)


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



def test_clm_provider_uses_shared_transport_policy_and_auth(monkeypatch):
    monkeypatch.setenv("BENCHMARK_MAX_RETRIES", "2")
    monkeypatch.setenv("BENCHMARK_TIMEOUT_SECONDS", "17")
    monkeypatch.setenv("CLM_API_KEY", "secret-token")

    provider = CLMProvider(base_url="http://clm.test")
    captured = {}

    class _Transport:
        policy = TransportPolicy(max_retries=2, timeout_seconds=17)

        def request(self, method, url, *, payload=None, headers=None):
            captured.update(
                {
                    "method": method,
                    "url": url,
                    "payload": payload,
                    "headers": headers,
                }
            )
            return JsonHttpResponse(
                body={"answers": {}, "model": "clm-latest"},
                headers={"X-CLM-Latency-Ms": "4.5"},
                status_code=200,
            )

    provider.transport = _Transport()
    body, latency = provider._post({"state": "fixture"})

    assert provider.transport_policy == TransportPolicy(
        max_retries=2,
        timeout_seconds=17,
    )
    assert provider.timeout == 17
    assert captured == {
        "method": "POST",
        "url": "http://clm.test/v1/systemone",
        "payload": {"state": "fixture"},
        "headers": {"Authorization": "Bearer secret-token"},
    }
    assert body["model"] == "clm-latest"
    assert latency == 4.5



def test_clm_provider_can_report_benchmark_runtime_identity_separately():
    provider = CLMProvider(
        model="clm-latest",
        benchmark_model_id="clm-v0.1-8b-q4km-outq2",
    )
    provider._post = lambda payload: (
        {
            "model": "clm-latest",
            "answers": {
                "intent": {
                    "type": "choice",
                    "choice": "billing",
                    "confidence": 0.9,
                    "probabilities": {"billing": 0.9, "support": 0.1},
                }
            },
            "usage": {},
        },
        5.0,
    )
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose one.",
        criteria={"billing": "Billing", "support": "Support"},
    )

    result = provider.evaluate("charged twice", [question])

    assert result.valid is True
    assert result.model == "clm-v0.1-8b-q4km-outq2"
    assert result.raw["served_model"] == "clm-latest"
    assert result.raw["benchmark_model_id"] == "clm-v0.1-8b-q4km-outq2"
