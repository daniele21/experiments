from __future__ import annotations

import json
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
from benchmark_core.transports import create_openai_compatible_client
from openai import OpenAI

from model_capability_bench.providers.parsing import parse_chat_response_content


def _input_payload(request: InferenceRequest) -> str:
    payload: dict[str, Any] = {"input": request.input}
    if request.response_schema is not None:
        payload["response_schema"] = request.response_schema
    return json.dumps(payload, ensure_ascii=False)


def _local_api_cost(model: ResolvedModel) -> float | None:
    value = model.provider.options.get("local_provider_fee")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


class OpenAICompatibleJsonProvider:
    provider_id = "openai-compatible"

    def __init__(
        self,
        model: ResolvedModel,
        *,
        base_url: str,
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
        self.client = create_openai_compatible_client(
            OpenAI,
            policy=policy,
            base_url=base_url,
            api_key=api_key,
        )

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            messages: list[dict[str, Any]] = []
            canonical_sys = self.resolved.model.metadata.get("system_prompt")
            if canonical_sys is not None:
                system_prompt = canonical_sys if canonical_sys != "none" else None
            else:
                system_prompt = request.system_prompt

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            for message in request.messages:
                messages.append(
                    {
                        "role": message.role,
                        "content": message.content,
                        **({"name": message.name} if message.name else {}),
                    }
                )

            raw_input = self.resolved.model.metadata.get("raw_input", False)
            output_format = self.resolved.model.metadata.get("output_format")
            if raw_input or output_format == "boxed":
                messages.append({"role": "user", "content": str(request.input)})
            else:
                messages.append({"role": "user", "content": _input_payload(request)})

            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "messages": messages,
            }
            supports_response_format = self.resolved.model.metadata.get(
                "supports_response_format", True
            )
            if supports_response_format and output_format != "boxed":
                kwargs["response_format"] = {"type": "json_object"}

            supports_temp = self.resolved.model.metadata.get(
                "supports_temperature", True
            )
            model_default_temp = self.resolved.model.metadata.get("default_temperature")
            model_default_top_p = self.resolved.model.metadata.get("default_top_p")

            if supports_temp is not False:
                if model_default_temp is not None and (
                    request.generation.temperature is None
                    or request.generation.temperature == 0.0
                ):
                    kwargs["temperature"] = float(model_default_temp)
                elif request.generation.temperature is not None:
                    kwargs["temperature"] = float(request.generation.temperature)

            if request.generation.max_output_tokens is not None:
                kwargs["max_tokens"] = request.generation.max_output_tokens

            supports_seed = self.resolved.model.metadata.get("supports_seed", True)
            if request.generation.seed is not None and supports_seed is not False:
                kwargs["seed"] = request.generation.seed

            top_p_override = None
            if request.generation.extra and "top_p" in request.generation.extra:
                top_p_override = float(request.generation.extra["top_p"])
            elif model_default_top_p is not None:
                top_p_override = float(model_default_top_p)

            if top_p_override is not None:
                kwargs["top_p"] = top_p_override

            if request.generation.stop:
                kwargs["stop"] = list(request.generation.stop)
            if request.generation.extra:
                extra_clean = {
                    k: v
                    for k, v in request.generation.extra.items()
                    if k not in ("top_p", "temperature")
                }
                if extra_clean:
                    kwargs["extra_body"] = extra_clean

            response = self.client.chat.completions.create(**kwargs)
            return self._parse_chat_result(response, started, request=request)
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes evidence
            err_msg = str(exc).lower()
            needs_retry = False
            if "temperature" in err_msg and "temperature" in kwargs:
                kwargs.pop("temperature", None)
                needs_retry = True
            if "top_p" in err_msg and "top_p" in kwargs:
                kwargs.pop("top_p", None)
                needs_retry = True
            if "seed" in err_msg and "seed" in kwargs:
                kwargs.pop("seed", None)
                needs_retry = True
            if needs_retry:
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    return self._parse_chat_result(response, started, request=request)
                except Exception as retry_exc:  # noqa: BLE001
                    exc = retry_exc

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
                estimated_cost_usd=_local_api_cost(self.resolved),
                metadata={"protocol": "chat-completions"},
            )

    def _parse_chat_result(
        self,
        response: Any,
        started: float,
        request: InferenceRequest | None = None,
    ) -> InferenceResult:
        latency_ms = (time.perf_counter() - started) * 1000
        content = response.choices[0].message.content or ""
        output_format = self.resolved.model.metadata.get("output_format")
        response_schema = request.response_schema if request else None
        parsed = parse_chat_response_content(
            content,
            response_schema=response_schema,
            output_format=output_format,
        )
        usage = getattr(response, "usage", None)
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_output=response,
            normalized_output=parsed,
            latency_ms=latency_ms,
            usage=TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
            ),
            estimated_cost_usd=_local_api_cost(self.resolved),
            metadata={"protocol": "chat-completions"},
        )


class OpenAIResponsesJsonProvider:
    provider_id = "openai"

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
        self.client = create_openai_compatible_client(
            OpenAI,
            policy=policy,
            api_key=api_key,
        )

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            kwargs: dict[str, Any] = {
                "model": self.model_id,
                "input": _input_payload(request),
            }
            if request.system_prompt:
                kwargs["instructions"] = request.system_prompt
            if request.response_schema is not None:
                schema = dict(request.response_schema)
                properties = schema.get("properties")
                required = set(schema.get("required") or [])
                all_required = isinstance(properties, Mapping) and all(
                    p in required for p in properties
                )
                kwargs["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "benchmark_response",
                        "strict": bool(all_required),
                        "schema": schema,
                    }
                }
            if request.generation.max_output_tokens is not None:
                kwargs["max_output_tokens"] = request.generation.max_output_tokens
            supports_temp = self.resolved.model.metadata.get("supports_temperature", True)
            if request.generation.temperature is not None and supports_temp is not False:
                kwargs["temperature"] = request.generation.temperature
            kwargs.update(dict(request.generation.extra))

            response = self.client.responses.create(**kwargs)
            return self._parse_responses_result(response, started)
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes evidence
            err_msg = str(exc).lower()
            needs_retry = False
            if "temperature" in err_msg and "temperature" in kwargs:
                kwargs.pop("temperature", None)
                needs_retry = True
            if (
                ("invalid_json_schema" in err_msg or "required" in err_msg)
                and "text" in kwargs
                and isinstance(kwargs.get("text"), dict)
                and "format" in kwargs["text"]
            ):
                kwargs["text"]["format"]["strict"] = False
                needs_retry = True
            if needs_retry:
                try:
                    response = self.client.responses.create(**kwargs)
                    return self._parse_responses_result(response, started)
                except Exception as retry_exc:  # noqa: BLE001
                    exc = retry_exc

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
                metadata={"protocol": "responses"},
            )

    def _parse_responses_result(
        self, response: Any, started: float
    ) -> InferenceResult:
        latency_ms = (time.perf_counter() - started) * 1000
        output_text = getattr(response, "output_text", "") or ""
        parsed = json.loads(output_text)
        usage = getattr(response, "usage", None)
        input_details = getattr(usage, "input_tokens_details", None)
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_output=response,
            normalized_output=parsed,
            latency_ms=latency_ms,
            usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                cached_input_tokens=getattr(input_details, "cached_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            ),
            estimated_cost_usd=None,
            metadata={"protocol": "responses"},
        )
