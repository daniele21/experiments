from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from openai import OpenAI

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider

DEFAULT_KORGIS_MODELS = [
    "nemotron-nano-4b",
    "qwen3-vl-4b",
]


class KorgisController:
    """Small control-plane client for reproducible local benchmark runs."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.api_base = (base_url or os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1")).rstrip("/")
        self.root = self.api_base.removesuffix("/v1")
        self.timeout = timeout or float(os.getenv("KORGIS_CONTROL_TIMEOUT_SECONDS", "360"))

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.root}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def resident_models(self) -> set[str]:
        payload = self._request("GET", "/v1/models")
        resident: set[str] = set()
        for item in payload.get("data", []):
            for key in ("key", "id"):
                value = item.get(key)
                if value:
                    resident.add(str(value))
        return resident

    def activate(self, model: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/models/activate",
            {"model": model},
        )

    def unload(self, model: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/models/{model}")

    def identity(self) -> dict[str, Any]:
        return self._request("GET", "/v1/runtime/identity")

    def model_identity(self, model: str) -> dict[str, Any] | None:
        payload = self.identity()
        models = payload.get("models") or {}
        identity = models.get(model)
        if identity is None:
            return None
        return {
            "protocol_version": payload.get("protocol_version"),
            "server": payload.get("server"),
            "default_model": payload.get("default_model"),
            "model": identity,
        }


class KorgisProvider(DecisionProvider):
    """OpenAI-compatible local decision baseline served by Korgis.

    Korgis provides the runtime/lifecycle boundary; this adapter owns only the
    benchmark prompt, strict result validation and measurement at the client edge.
    Local API cost is zero. Hardware, energy and amortisation cost are intentionally
    not represented as zero and remain outside estimated API cost.
    """

    name = "local-korgis"

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        *,
        seed: int = 42,
    ) -> None:
        self.model = model
        self.base_url = (
            base_url or os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1")
        ).rstrip("/")
        timeout = float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60"))
        self.seed = seed
        self.max_tokens = int(os.getenv("KORGIS_MAX_OUTPUT_TOKENS", "2048"))
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=os.getenv("KORGIS_API_KEY", "local"),
            max_retries=0,
            timeout=timeout,
        )

    @staticmethod
    def _question_payload(question: QuestionSpec) -> dict[str, Any]:
        return {
            "id": question.id,
            "type": question.type,
            "instructions": question.instructions,
            "criteria": question.criteria,
        }

    @staticmethod
    def _coerce_probability(value: Any) -> float:
        """Accept common bounded probability encodings without semantic repair."""
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            probability = float(value)
        elif isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes"}:
                return 1.0
            if normalized in {"false", "no"}:
                return 0.0
            probability = float(normalized)
        else:
            raise TypeError(f"unsupported probability value: {value!r}")
        if not 0 <= probability <= 1:
            raise ValueError("probability outside [0,1]")
        return probability

    def evaluate(self, state: Any, questions: Sequence[QuestionSpec]) -> ProviderResult:
        started = time.perf_counter()
        try:
            prompt = {
                "task": (
                    "Evaluate every question independently against the same state. "
                    "Return exactly one JSON object with an 'answers' array and no prose. "
                    "Return exactly one answer for every supplied question and use each supplied "
                    "question id exactly once. Do not invent ids. "
                    "Each answer must contain id, value, confidence and selected_probability. "
                    "For Choice, value must be exactly one supplied option. "
                    "For Noul, value is the probability of YES from 0 to 1; JSON true/false is "
                    "also accepted as 1/0. For Score, value is numeric. "
                    "confidence is a 0-1 confidence score. selected_probability is a 0-1 "
                    "estimate that the selected answer is correct."
                ),
                "state": state,
                "required_answer_ids": [question.id for question in questions],
                "answer_contract": {
                    "answer_count": len(questions),
                    "required_fields": [
                        "id",
                        "value",
                        "confidence",
                        "selected_probability",
                    ],
                },
                "questions": [self._question_payload(question) for question in questions],
            }
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a bounded decision engine. Follow the supplied choices "
                            "exactly and output valid JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=self.max_tokens,
                seed=self.seed,
                extra_body={
                    "enable_thinking": False,
                    "show_thinking": False,
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            content = response.choices[0].message.content or ""
            data = json.loads(content)
            items = data.get("answers")
            if not isinstance(items, list):
                raise TypeError("response JSON has no answers array")

            by_id = {question.id: question for question in questions}
            decisions: dict[str, Decision] = {}
            errors: list[str] = []

            for item in items:
                if not isinstance(item, dict):
                    errors.append("answer is not an object")
                    continue
                qid = str(item.get("id") or "")
                if qid not in by_id:
                    errors.append(f"unexpected question id {qid!r}")
                    continue
                question = by_id[qid]
                value = item.get("value")
                confidence = self._coerce_probability(item.get("confidence"))
                selected_probability = self._coerce_probability(
                    item.get("selected_probability")
                )

                if question.type == "choice":
                    if not isinstance(question.criteria, dict) or str(value) not in question.criteria:
                        errors.append(f"{qid}: value outside allowed choices")
                elif question.type == "noul":
                    value = self._coerce_probability(value)
                    selected_probability = max(value, 1.0 - value)
                elif question.type == "score":
                    value = float(value)

                decisions[qid] = Decision(
                    question_id=qid,
                    value=value,
                    probabilities={},
                    confidence=confidence,
                    predicted_probability=selected_probability,
                )

            if set(decisions) != set(by_id):
                missing = sorted(set(by_id) - set(decisions))
                errors.append(f"missing question answers: {missing}")

            usage = getattr(response, "usage", None)
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers=decisions,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "prompt_tokens", None),
                cached_input_tokens=0,
                output_tokens=getattr(usage, "completion_tokens", None),
                estimated_cost_usd=0.0,
                valid=not errors,
                error="; ".join(errors) or None,
                raw=response,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary records failures
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers={},
                latency_ms=(time.perf_counter() - started) * 1000,
                estimated_cost_usd=0.0,
                valid=False,
                error=f"{type(exc).__name__}: {exc}",
            )


def ensure_korgis_models_resident(
    controller: KorgisController,
    models: Sequence[str],
) -> None:
    resident = controller.resident_models()
    missing = [model for model in models if model not in resident]
    if missing:
        raise RuntimeError(
            "Korgis models are not resident: "
            + ", ".join(missing)
            + ". Start Korgis with these models or use managed runtime switching."
        )


def managed_korgis_model_order(
    models: Sequence[str],
    anchor_model: str,
) -> list[str]:
    unique = list(dict.fromkeys(models))
    if anchor_model in unique:
        return [model for model in unique if model != anchor_model] + [anchor_model]
    return unique
