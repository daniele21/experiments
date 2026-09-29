from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from openai import OpenAI

from redact_bench.models import Case, Finding, InferenceResult
from redact_bench.postprocess import resolve_model_payload
from redact_bench.profiles import (
    build_system_prompt,
    load_contract_metadata,
    load_profiles,
)
from redact_bench.resilient_evaluator import (
    ResilientExecutionSettings,
    clean_exception_details,
    evaluate_case_resiliently,
)
from redact_bench.segmentation import TextSegment, segment_text


class KorgisUnavailableError(RuntimeError):
    """Raised when the external Korgis control plane cannot be reached."""

    def __init__(self, *, api_base: str, detail: str) -> None:
        self.api_base = api_base
        self.detail = detail
        super().__init__(f"Korgis is not reachable at {api_base}. {detail}")


DEFAULT_MODELS = [
    "nemotron-nano-4b",
    "nemotron-nano-4b-q8",
    "qwen3.5-4b-q4km",
    "qwen3.5-9b-q4km",
]


class KorgisController:
    def __init__(self, base_url: str | None = None) -> None:
        self.api_base = (
            base_url
            or os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1")
        ).rstrip("/")
        self.root = self.api_base.removesuffix("/v1")
        self.timeout = float(os.getenv("KORGIS_CONTROL_TIMEOUT_SECONDS", "360"))

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        encoded = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.root + path,
            data=encoded,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise KorgisUnavailableError(
                api_base=self.api_base,
                detail=f"{type(reason).__name__}: {reason}",
            ) from exc

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
    def __init__(
        self,
        model: str,
        profiles_path: str,
        *,
        timeout: float | None = None,
        chunk_max_chars: int | None = None,
        chunk_overlap_chars: int | None = None,
        max_output_tokens: int | None = None,
        adaptive_subdivision: bool | None = None,
    ) -> None:
        self.model = model
        self.profiles_path = profiles_path
        base_url = os.getenv(
            "KORGIS_BASE_URL",
            "http://127.0.0.1:1235/v1",
        ).rstrip("/")
        contract = load_contract_metadata(profiles_path)
        self.max_tokens = int(
            max_output_tokens
            if max_output_tokens is not None
            else os.getenv(
                "REDACT_BENCH_MAX_OUTPUT_TOKENS",
                str(contract.get("max_output_tokens", 4096)),
            )
        )
        self.chunk_max_chars = int(
            chunk_max_chars
            if chunk_max_chars is not None
            else os.getenv(
                "REDACT_BENCH_CHUNK_MAX_CHARS",
                str(contract.get("chunk_max_chars", 4000)),
            )
        )
        self.chunk_overlap_chars = int(
            chunk_overlap_chars
            if chunk_overlap_chars is not None
            else os.getenv(
                "REDACT_BENCH_CHUNK_OVERLAP_CHARS",
                str(contract.get("chunk_overlap_chars", 256)),
            )
        )
        self.timeout = float(
            timeout
            if timeout is not None
            else os.getenv(
                "BENCHMARK_TIMEOUT_SECONDS",
                str(contract.get("benchmark_timeout_seconds", 360)),
            )
        )
        effective_adaptive = (
            adaptive_subdivision
            if adaptive_subdivision is not None
            else os.getenv("REDACT_BENCH_ADAPTIVE_SUBDIVISION", "1").lower() not in {"0", "false", "no"}
        )
        self.settings = ResilientExecutionSettings(
            timeout_seconds=self.timeout,
            chunk_max_chars=self.chunk_max_chars,
            chunk_overlap_chars=self.chunk_overlap_chars,
            max_output_tokens=self.max_tokens,
            adaptive_subdivision=effective_adaptive,
        )
        self.execution_settings = {
            "max_output_tokens": self.max_tokens,
            "chunk_max_chars": self.chunk_max_chars,
            "chunk_overlap_chars": self.chunk_overlap_chars,
            "benchmark_timeout_seconds": self.timeout,
            "adaptive_subdivision": effective_adaptive,
        }
        self.client = OpenAI(
            base_url=base_url,
            api_key=os.getenv("KORGIS_API_KEY", "local"),
            timeout=self.timeout,
            max_retries=0,
        )

    def evaluate(self, case: Case) -> InferenceResult:
        """Evaluate one case using bounded segmentation with adaptive subdivision."""
        return evaluate_case_resiliently(
            case,
            model=self.model,
            evaluator=self._evaluate_segment,
            settings=self.settings,
        )

    def _evaluate_segment(
        self,
        case: Case,
        segment: TextSegment,
    ) -> InferenceResult:
        started = time.perf_counter()
        content = ""
        finish_reason: str | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": build_system_prompt(
                            case.profile,
                            self.profiles_path,
                        ),
                    },
                    {"role": "user", "content": segment.text},
                ],
                temperature=0,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                extra_body={
                    "enable_thinking": False,
                    "show_thinking": False,
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = (
                str(choice.finish_reason)
                if choice.finish_reason is not None
                else None
            )
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)

            if finish_reason in {"length", "max_tokens"}:
                return self._failure(
                    case=case,
                    started=started,
                    latency_ms=latency_ms,
                    status="truncated_output",
                    error_type="truncated_output",
                    error=f"finish_reason={finish_reason}",
                    raw_content=content,
                    finish_reason=finish_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            if not content:
                return self._failure(
                    case=case,
                    started=started,
                    latency_ms=latency_ms,
                    status="invalid_response",
                    error_type="empty_content",
                    error="assistant content is empty",
                    raw_content=content,
                    finish_reason=finish_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            try:
                payload = json.loads(content)
            except json.JSONDecodeError as exc:
                return self._failure(
                    case=case,
                    started=started,
                    latency_ms=latency_ms,
                    status="invalid_json",
                    error_type="JSONDecodeError",
                    error=f"line={exc.lineno} column={exc.colno}: {exc.msg}",
                    raw_content=content,
                    finish_reason=finish_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            schema_error = self._validate_payload(case.profile, payload)
            if schema_error is not None:
                return self._failure(
                    case=case,
                    started=started,
                    latency_ms=latency_ms,
                    status="invalid_schema",
                    error_type="invalid_schema",
                    error=schema_error,
                    raw_content=content,
                    finish_reason=finish_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            resolution = resolve_model_payload(segment.text, payload)
            return InferenceResult(
                case_id=case.case_id,
                model=self.model,
                valid=True,
                latency_ms=latency_ms,
                findings=resolution.findings,
                raw_content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                status="success",
                finish_reason=finish_reason,
                raw_item_count=len(payload["pii_fields"]),
                resolved_item_count=resolution.resolved_items,
                unresolved_item_count=resolution.unresolved_items,
            )
        except Exception as exc:
            error_msg, status, status_code = clean_exception_details(exc, self.timeout)
            return self._failure(
                case=case,
                started=started,
                status=status,
                error_type=type(exc).__name__,
                error=error_msg,
                http_status=status_code,
                raw_content=content,
                finish_reason=finish_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

    def _validate_payload(
        self,
        profile: str,
        payload: Any,
    ) -> str | None:
        if not isinstance(payload, dict):
            return "response JSON is not an object"
        fields = payload.get("pii_fields")
        if not isinstance(fields, list):
            return "response JSON has no pii_fields array"

        definitions = load_profiles(self.profiles_path).get(profile, {})
        allowed = set(definitions)
        for index, field in enumerate(fields):
            if not isinstance(field, dict):
                return f"pii_fields[{index}] is not an object"
            pii_type = field.get("pii_type")
            value = field.get("value")
            if not isinstance(pii_type, str) or not pii_type:
                return f"pii_fields[{index}].pii_type is missing"
            if pii_type not in allowed:
                return f"pii_fields[{index}].pii_type={pii_type!r} is not allowed"
            if not isinstance(value, str) or not value.strip():
                return f"pii_fields[{index}].value is missing"
        return None

    def _failure(
        self,
        *,
        case: Case,
        started: float,
        status: str,
        error_type: str,
        error: str,
        raw_content: str,
        latency_ms: float | None = None,
        http_status: int | None = None,
        finish_reason: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> InferenceResult:
        return InferenceResult(
            case_id=case.case_id,
            model=self.model,
            valid=False,
            latency_ms=(
                latency_ms
                if latency_ms is not None
                else (time.perf_counter() - started) * 1000
            ),
            findings=[],
            raw_content=raw_content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
            status=status,
            error_type=error_type,
            http_status=http_status,
            finish_reason=finish_reason,
            segment_count=1,
            successful_segments=0,
            failed_segment_index=0,
        )


def _add_optional(current: int | None, value: int | None) -> int | None:
    if value is None:
        return current
    return (current or 0) + int(value)
