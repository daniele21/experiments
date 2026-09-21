from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from openai import OpenAI

from redact_bench.models import Case, InferenceResult
from redact_bench.postprocess import findings_from_model_payload
from redact_bench.profiles import build_system_prompt


DEFAULT_MODELS = [
    "nemotron-nano-4b",
    "nemotron-nano-4b-q8",
    "qwen3.5-4b-q4km",
    "qwen3.5-9b-q4km",
]


class KorgisController:
    def __init__(self, base_url: str | None = None) -> None:
        self.api_base = (base_url or os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1")).rstrip("/")
        self.root = self.api_base.removesuffix("/v1")
        self.timeout = float(os.getenv("KORGIS_CONTROL_TIMEOUT_SECONDS", "360"))

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        encoded = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.root + path,
            data=encoded,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def registry(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/models/registry")

    def activate(self, model: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/models/activate", {"model": model})

    def unload(self, model: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/models/{model}")

    def identity(self) -> dict[str, Any]:
        return self._request("GET", "/v1/runtime/identity")

    def model_identity(self, model: str) -> dict[str, Any] | None:
        payload = self.identity()
        identity = (payload.get("models") or {}).get(model)
        if identity is None:
            return None
        return {
            "protocol_version": payload.get("protocol_version"),
            "server": payload.get("server"),
            "default_model": payload.get("default_model"),
            "model": identity,
        }


class KorgisRedactProvider:
    def __init__(self, model: str, profiles_path: str) -> None:
        self.model = model
        self.profiles_path = profiles_path
        base_url = os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1").rstrip("/")
        self.max_tokens = int(os.getenv("REDACT_BENCH_MAX_OUTPUT_TOKENS", "2048"))
        self.client = OpenAI(
            base_url=base_url,
            api_key=os.getenv("KORGIS_API_KEY", "local"),
            timeout=float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "120")),
            max_retries=0,
        )

    def evaluate(self, case: Case) -> InferenceResult:
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": build_system_prompt(case.profile, self.profiles_path),
                    },
                    {"role": "user", "content": case.text},
                ],
                temperature=0,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": False, "show_thinking": False},
            )
            latency_ms = (time.perf_counter() - started) * 1000
            content = response.choices[0].message.content or ""
            payload = json.loads(content)
            findings = findings_from_model_payload(case.text, payload)
            usage = getattr(response, "usage", None)
            return InferenceResult(
                case_id=case.case_id,
                model=self.model,
                valid=True,
                latency_ms=latency_ms,
                findings=findings,
                raw_content=content,
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
            )
        except Exception as exc:  # provider boundary intentionally records all failures
            return InferenceResult(
                case_id=case.case_id,
                model=self.model,
                valid=False,
                latency_ms=(time.perf_counter() - started) * 1000,
                findings=[],
                raw_content="",
                error=f"{type(exc).__name__}: {exc}",
            )
