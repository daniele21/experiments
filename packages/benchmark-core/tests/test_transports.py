from __future__ import annotations

import io
import urllib.error
from types import SimpleNamespace

import pytest

from benchmark_core.transports import (
    JsonHttpTransport,
    TransportError,
    TransportPolicy,
    create_openai_compatible_client,
    inference_error_from_exception,
    resolve_transport_policy,
)


class _FakeResponse:
    def __init__(self, body: str, *, status: int = 200, headers=None) -> None:
        self._body = body.encode("utf-8")
        self.status = status
        self.headers = headers or {"X-Test": "ok"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_transport_policy_resolves_from_environment() -> None:
    policy = resolve_transport_policy(
        {
            "BENCHMARK_MAX_RETRIES": "2",
            "BENCHMARK_TIMEOUT_SECONDS": "15.5",
        },
        default_max_retries=0,
        default_timeout_seconds=60,
    )

    assert policy == TransportPolicy(max_retries=2, timeout_seconds=15.5)


def test_openai_compatible_client_receives_only_transport_options() -> None:
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kind="client")

    client = create_openai_compatible_client(
        factory,
        policy=TransportPolicy(max_retries=3, timeout_seconds=20),
        base_url="http://localhost:1234/v1",
        api_key="secret",
    )

    assert client.kind == "client"
    assert captured == {
        "max_retries": 3,
        "timeout": 20,
        "base_url": "http://localhost:1234/v1",
        "api_key": "secret",
    }


def test_json_http_transport_retries_retryable_http_error() -> None:
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        assert timeout == 10
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "unavailable",
                {},
                io.BytesIO(b"try again"),
            )
        return _FakeResponse('{"ok": true}')

    transport = JsonHttpTransport(
        TransportPolicy(max_retries=1, timeout_seconds=10),
        opener=opener,
    )
    response = transport.request("POST", "http://example.test", payload={"a": 1})

    assert calls == 2
    assert response.body == {"ok": True}
    assert response.headers["X-Test"] == "ok"


def test_json_http_transport_exposes_typed_auth_failure() -> None:
    def opener(request, *, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "unauthorized",
            {},
            io.BytesIO(b"bad token"),
        )

    transport = JsonHttpTransport(
        TransportPolicy(max_retries=0, timeout_seconds=10),
        opener=opener,
    )

    with pytest.raises(TransportError) as error:
        transport.request("GET", "http://example.test")

    assert error.value.kind == "authentication"
    assert error.value.status_code == 401
    assert error.value.retryable is False

    inference_error = inference_error_from_exception(error.value)
    assert inference_error.kind == "authentication"
    assert inference_error.details["status_code"] == 401



def test_json_http_transport_rejects_invalid_json() -> None:
    transport = JsonHttpTransport(
        TransportPolicy(max_retries=0, timeout_seconds=10),
        opener=lambda request, timeout: _FakeResponse("not-json"),
    )

    with pytest.raises(TransportError) as error:
        transport.request("GET", "http://example.test")

    assert error.value.kind == "invalid_response"
    assert error.value.retryable is False
    assert error.value.detail == "not-json"


def test_json_http_transport_normalizes_timeout() -> None:
    calls = 0

    def opener(request, *, timeout):
        nonlocal calls
        calls += 1
        raise TimeoutError("slow provider")

    transport = JsonHttpTransport(
        TransportPolicy(max_retries=1, timeout_seconds=5),
        opener=opener,
    )

    with pytest.raises(TransportError) as error:
        transport.request("GET", "http://example.test")

    assert calls == 2
    assert error.value.kind == "timeout"
    assert error.value.retryable is True
    assert str(error.value) == "slow provider"
