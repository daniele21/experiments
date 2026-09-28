"""Connection preflight for an externally managed CLM System One endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any


def normalize_clm_base_url(value: str) -> str:
    """Return the CLM root URL even when a caller supplies a /v1 suffix."""
    root = value.strip().rstrip("/").removesuffix("/v1")
    if not root:
        raise ValueError("CLM base URL must not be empty")
    return root


class CLMEndpoint:
    """Small read-only client used to validate CLM before benchmark execution."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = normalize_clm_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, *, timeout: float | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout or self.timeout,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"CLM HTTP {exc.code} from {path}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach CLM endpoint {self.base_url}: {exc.reason}"
            ) from exc
        if not isinstance(payload, dict):
            raise TypeError(f"CLM {path} did not return a JSON object")
        return payload

    def preflight(self, requested_models: Sequence[str]) -> dict[str, Any]:
        """Fail fast unless the runtime and every requested model are ready."""
        health = self._get("/health", timeout=min(self.timeout, 5.0))
        if not health.get("ok"):
            raise RuntimeError(f"CLM health check failed: {health}")

        models_payload = self._get("/v1/models", timeout=min(self.timeout, 10.0))
        raw_models = models_payload.get("models")
        if not isinstance(raw_models, list):
            raise TypeError("CLM /v1/models response has no models array")

        served = {
            str(item.get("name"))
            for item in raw_models
            if isinstance(item, dict) and item.get("name")
        }
        missing = [model for model in requested_models if model not in served]
        if missing:
            raise RuntimeError(
                "Requested CLM model(s) are not served: "
                + ", ".join(missing)
                + f". Served: {', '.join(sorted(served)) or '<none>'}"
            )

        return {
            "base_url": self.base_url,
            "served_models": sorted(served),
            "embedder_healthy": bool(health.get("embedder")),
            "mock": bool(health.get("mock", False)),
        }
