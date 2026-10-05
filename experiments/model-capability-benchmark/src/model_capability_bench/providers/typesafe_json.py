from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from benchmark_core import (
    InferenceError,
    InferenceRequest,
    InferenceResult,
    ResolvedModel,
    TokenUsage,
    inference_error_from_exception,
    resolve_transport_policy,
)
from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient


class TypeSafeJevJsonProvider:
    provider_id = "typesafe"

    def __init__(
        self,
        model: ResolvedModel,
        *,
        api_key: str,
        environ: Mapping[str, str],
    ) -> None:
        self.resolved = model
        self.provider_id = model.provider.provider_key
        self.model_id = model.effective_model_id
        policy = resolve_transport_policy(
            environ,
            default_max_retries=0,
            default_timeout_seconds=60,
        )
        self.client = TypeSafeClient(
            api_key=api_key,
            retry=RetryPolicy(max_retries=policy.max_retries),
            timeout=policy.timeout_seconds,
        )

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            schema = request.response_schema or {}
            properties = (
                schema.get("properties")
                if isinstance(schema, Mapping)
                else None
            )
            if not properties or not isinstance(properties, Mapping):
                raise ValueError(
                    "Jev only supports bounded classification/decision tasks with a defined response schema."
                )

            enum_field = None
            enum_values = None
            for key, prop in properties.items():
                if isinstance(prop, Mapping) and "enum" in prop:
                    enum_field = key
                    enum_values = prop["enum"]
                    break

            if enum_field is None or not enum_values:
                raise ValueError(
                    f"Jev requires a discrete choice/enum field in response schema. Found: {list(properties.keys())}"
                )

            state: dict[str, Any]
            if isinstance(request.input, Mapping):
                state = dict(request.input)
            elif isinstance(request.input, str):
                state = {"text": request.input}
            else:
                state = {"input": request.input}

            criteria = {
                str(val): str(val).replace("_", " ")
                for val in enum_values
            }
            question = Choice(
                instructions=request.system_prompt or "Select the best matching category.",
                criteria=criteria,
            )

            response = self.client.system_one(
                state=state,
                model=self.model_id,
                questions={enum_field: question},
            )
            latency_ms = (time.perf_counter() - started) * 1000

            ans = response.answers[enum_field]
            choice = ans.choice
            confidence = float(getattr(ans, "confidence", 1.0))

            normalized: dict[str, Any] = {enum_field: choice}
            if "confidence" in properties:
                normalized["confidence"] = confidence

            usage = getattr(response, "usage", None)
            resolved_model = getattr(response, "model", self.model_id)
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)

            raw_dump: Any
            if hasattr(response, "model_dump"):
                raw_dump = response.model_dump()
            elif hasattr(response, "dict"):
                raw_dump = response.dict()
            else:
                raw_dump = str(response)

            return InferenceResult(
                provider_id=self.provider_id,
                model_id=resolved_model,
                raw_output=raw_dump,
                normalized_output=normalized,
                latency_ms=latency_ms,
                usage=TokenUsage(
                    input_tokens=input_tokens,
                    cached_input_tokens=0,
                    output_tokens=output_tokens,
                ),
                estimated_cost_usd=None,
                metadata={"protocol": "system-one"},
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes evidence
            error = inference_error_from_exception(exc)
            if error.kind == "unknown":
                error = InferenceError(
                    kind="provider",
                    message=error.message,
                    retryable=False,
                )
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output=None,
                normalized_output=None,
                latency_ms=(time.perf_counter() - started) * 1000,
                valid=False,
                error=error,
                estimated_cost_usd=None,
                metadata={"protocol": "system-one"},
            )
