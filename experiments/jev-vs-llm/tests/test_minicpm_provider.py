from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from jev_bench.models import QuestionSpec
from jev_bench.providers import minicpm as minicpm_module
from jev_bench.providers.minicpm import MiniCPMProvider


class _FakeChatCompletions:
    def create(self, **kwargs):
        assert kwargs["model"] == "MiniCPM-V-4.6-1B"
        assert kwargs["temperature"] == 0.0
        payload = {
            "answers": [
                {
                    "id": "intent",
                    "value": "billing",
                    "confidence": 0.81,
                    "selected_probability": 0.79,
                }
            ]
        }
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
            usage=SimpleNamespace(prompt_tokens=101, completion_tokens=19),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())


def test_minicpm_provider_uses_official_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class _ClientFactory:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = _FakeClient().chat

    monkeypatch.setenv("MINICPM_API_KEY", "test-key")
    monkeypatch.delenv("MINICPM_BASE_URL", raising=False)
    monkeypatch.delenv("MINICPM_MODEL", raising=False)
    monkeypatch.setattr(minicpm_module, "OpenAI", _ClientFactory)

    provider = MiniCPMProvider()

    assert provider.model == "MiniCPM-V-4.6-1B"
    assert provider.base_url == "https://api.modelbest.cn/v1"
    assert captured["base_url"] == "https://api.modelbest.cn/v1"
    assert captured["api_key"] == "test-key"


def test_minicpm_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("MINICPM_API_KEY", raising=False)

    with pytest.raises(ValueError, match="MINICPM_API_KEY"):
        MiniCPMProvider()


def test_minicpm_provider_parses_bounded_json(monkeypatch):
    monkeypatch.setenv("MINICPM_API_KEY", "test-key")
    provider = MiniCPMProvider()
    provider.client = _FakeClient()
    question = QuestionSpec(
        id="intent",
        type="choice",
        instructions="Choose one intent.",
        criteria={"billing": "Billing", "support": "Support"},
    )

    result = provider.evaluate("I was charged twice.", [question])

    assert result.valid is True
    assert result.provider == "minicpm-api"
    assert result.model == "MiniCPM-V-4.6-1B"
    assert result.answers["intent"].value == "billing"
    assert result.input_tokens == 101
    assert result.output_tokens == 19
    assert result.estimated_cost_usd is None
