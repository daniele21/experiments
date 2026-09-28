from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

from redact_bench.models import Case, Span
from redact_bench.provider import (
    KorgisController,
    KorgisRedactProvider,
    KorgisUnavailableError,
)


def test_korgis_connection_refused_has_actionable_error(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr("urllib.request.urlopen", fail)

    controller = KorgisController("http://127.0.0.1:1235/v1")
    with pytest.raises(KorgisUnavailableError) as exc_info:
        controller.health()

    message = str(exc_info.value)
    assert "Korgis is not reachable" in message
    assert "http://127.0.0.1:1235/v1" in message
    assert "Connection refused" in message


class _Completions:
    def __init__(self, response):
        self.response = response

    def create(self, **_kwargs):
        return self.response


class _Client:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_Completions(response))


def _response(content: str, *, finish_reason: str = "stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
    )


def _provider(monkeypatch, response) -> KorgisRedactProvider:
    monkeypatch.setattr(
        "redact_bench.provider.OpenAI",
        lambda **_kwargs: _Client(response),
    )
    root = Path(__file__).resolve().parents[1]
    return KorgisRedactProvider(
        "test-model",
        str(root / "config/profiles.yaml"),
    )


def _case() -> Case:
    return Case(
        case_id="x",
        profile="financial",
        text="Cliente Mario Rossi.",
        gold=(Span(8, 19, "private_person", "Mario Rossi"),),
    )


def test_truncated_structured_output_is_typed_failure(monkeypatch):
    provider = _provider(
        monkeypatch,
        _response('{"pii_fields":[', finish_reason="length"),
    )

    result = provider.evaluate(_case())

    assert result.valid is False
    assert result.status == "truncated_output"
    assert result.finish_reason == "length"
    assert result.raw_content == '{"pii_fields":['
    assert result.output_tokens == 10


def test_invalid_json_is_not_zero_detection(monkeypatch):
    provider = _provider(
        monkeypatch,
        _response('{"pii_fields":'),
    )

    result = provider.evaluate(_case())

    assert result.valid is False
    assert result.status == "invalid_json"
    assert result.error_type == "JSONDecodeError"
    assert result.raw_content == '{"pii_fields":'


def test_minimal_contract_resolves_source_spans(monkeypatch):
    provider = _provider(
        monkeypatch,
        _response(
            '{"pii_fields":['
            '{"pii_type":"private_person","value":"Mario Rossi"}'
            ']}'
        ),
    )

    result = provider.evaluate(_case())

    assert result.valid is True
    assert result.status == "success"
    assert result.raw_item_count == 1
    assert result.resolved_item_count == 1
    assert result.unresolved_item_count == 0
    assert [(finding.start, finding.end) for finding in result.findings] == [(8, 19)]
