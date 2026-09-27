from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from benchmark_core.transports.errors import TransportError
from benchmark_core.transports.policy import TransportPolicy


@dataclass(frozen=True)
class JsonHttpResponse:
    body: Any
    headers: Mapping[str, str]
    status_code: int


class JsonHttpTransport:
    def __init__(
        self,
        policy: TransportPolicy,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.policy = policy
        self._opener = opener

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code == 429 or status_code >= 500

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> JsonHttpResponse:
        encoded = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(dict(headers or {}))
        request = urllib.request.Request(
            url,
            data=encoded,
            headers=request_headers,
            method=method.upper(),
        )

        attempts = self.policy.max_retries + 1
        for attempt in range(attempts):
            try:
                with self._opener(
                    request,
                    timeout=self.policy.timeout_seconds,
                ) as response:
                    raw = response.read().decode("utf-8")
                    try:
                        body = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise TransportError(
                            kind="invalid_response",
                            message="HTTP response was not valid JSON",
                            retryable=False,
                            detail=raw,
                        ) from exc
                    return JsonHttpResponse(
                        body=body,
                        headers=dict(response.headers.items()),
                        status_code=int(getattr(response, "status", 200)),
                    )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                retryable = self._retryable_status(exc.code)
                if retryable and attempt + 1 < attempts:
                    continue
                kind = "authentication" if exc.code in {401, 403} else "transport"
                raise TransportError(
                    kind=kind,
                    message=f"HTTP {exc.code}: {detail}",
                    retryable=retryable,
                    status_code=exc.code,
                    detail=detail,
                ) from exc
            except (TimeoutError, socket.timeout) as exc:
                if attempt + 1 < attempts:
                    continue
                raise TransportError(
                    kind="timeout",
                    message=str(exc) or "HTTP request timed out",
                    retryable=True,
                ) from exc
            except urllib.error.URLError as exc:
                if attempt + 1 < attempts:
                    continue
                raise TransportError(
                    kind="transport",
                    message=f"HTTP transport error: {exc.reason}",
                    retryable=True,
                ) from exc

        raise RuntimeError("unreachable transport state")
