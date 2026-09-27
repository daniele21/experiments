from __future__ import annotations

from collections.abc import Callable
from typing import Any

from benchmark_core.transports.policy import TransportPolicy


def create_openai_compatible_client(
    client_factory: Callable[..., Any],
    *,
    policy: TransportPolicy,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "max_retries": policy.max_retries,
        "timeout": policy.timeout_seconds,
    }
    if base_url is not None:
        kwargs["base_url"] = base_url
    if api_key is not None:
        kwargs["api_key"] = api_key
    return client_factory(**kwargs)
