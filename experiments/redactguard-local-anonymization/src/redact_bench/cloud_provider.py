"""Explicit OpenAI API reference provider, never the local Korgis transport.

Only the wire call changes. All prompts, PII taxonomy, segmentation, schema
validation, value-to-offset resolution and metrics are inherited from the
same local benchmark provider. The ChatGPT product session is NOT an API key.
"""
from __future__ import annotations

import os

from openai import OpenAI

from redact_bench.provider import KorgisRedactProvider
from redact_bench.models import Case
from redact_bench.segmentation import TextSegment


SUPPORTED_CLOUD_MODELS = ("gpt-6-luna",)


class OpenAICloudRedactProvider(KorgisRedactProvider):
    def __init__(self, model: str, profiles_path: str, **kwargs) -> None:
        if model not in SUPPORTED_CLOUD_MODELS:
            raise ValueError(f"Unsupported cloud benchmark model: {model}")
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for the cloud reference benchmark.")
        super().__init__(model, profiles_path, **kwargs)
        # Unlike Korgis, do not override base_url and do not silently point an
        # API-key-bearing client at another host. Deliberately opt out of SDK
        # retries so the measured cost and number of requests are predictable.
        self.client = OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                             timeout=self.timeout, max_retries=0)
        self.execution_settings.update({
            "backend": "openai_api",
            "model": model,
            "reasoning_effort": "none",
            "temperature": 0,
            "response_format": "json_object",
            "store": False,
            "api_retry_count": 0,
            "note": "Remote API network latency is not comparable to on-device Korgis latency",
        })

    def _completion_kwargs(self, case: Case, segment: TextSegment) -> dict:
        request=super()._completion_kwargs(case, segment)
        request.pop("extra_body", None)  # Korgis-only llama-server controls
        # GPT-6 Luna supports temperature when reasoning_effort="none".\n        # Keep the same temperature=0 as the local Korgis quality protocol.
        request["max_completion_tokens"]=request.pop("max_tokens")
        request["reasoning_effort"]="none"
        request["store"]=False
        return request
