from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any

from benchmark_core.transports import JsonHttpTransport, resolve_transport_policy

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


class CLMProvider(DecisionProvider):
    """Contrastive-LM System One provider using the official wire protocol.

    CLM is kept behind its HTTP boundary instead of imported as a benchmark
    dependency. The Qwen3-8B pooling encoder and CLM head may run on a remote
    accelerator or through the managed local llama.cpp GGUF runtime while the
    benchmark contract stays unchanged.
    """

    name = "clm"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        *,
        temperature: float | None = None,
        benchmark_model_id: str | None = None,
    ) -> None:
        self.model = model or os.getenv("CLM_MODEL", "clm-latest")
        self.benchmark_model_id = benchmark_model_id
        self.base_url = (
            base_url or os.getenv("CLM_BASE_URL", "http://127.0.0.1:8700")
        ).rstrip("/")
        self.api_key = os.getenv("CLM_API_KEY")
        self.transport_policy = resolve_transport_policy(
            os.environ,
            default_max_retries=0,
            default_timeout_seconds=60,
        )
        self.timeout = self.transport_policy.timeout_seconds
        self.transport = JsonHttpTransport(self.transport_policy)
        self.temperature = (
            float(os.getenv("CLM_TEMPERATURE", "1.0"))
            if temperature is None
            else float(temperature)
        )
        if not 0 < self.temperature <= 100:
            raise ValueError("CLM temperature must be in (0, 100]")

    @staticmethod
    def _question_payload(question: QuestionSpec) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": question.type,
            "instructions": question.instructions,
        }
        if question.type == "choice":
            if not isinstance(question.criteria, dict) or not question.criteria:
                raise ValueError(f"Choice {question.id} requires non-empty dict criteria")
            payload["criteria"] = dict(question.criteria)
        elif question.type == "score":
            if not isinstance(question.criteria, list) or len(question.criteria) < 2:
                raise ValueError(f"Score {question.id} requires at least two ordered levels")
            payload["criteria"] = list(question.criteria)
        elif question.type == "noul":
            if question.criteria is not None:
                if not isinstance(question.criteria, dict):
                    raise ValueError(f"Noul {question.id} criteria must be a dict when supplied")
                payload["criteria"] = dict(question.criteria)
        else:
            raise ValueError(f"Unsupported question type: {question.type}")
        return payload

    @staticmethod
    def _probabilities(value: Any) -> dict[str, float]:
        if not isinstance(value, dict) or not value:
            raise TypeError("answer probabilities must be a non-empty object")
        probabilities = {str(k): float(v) for k, v in value.items()}
        if any(
            probability < 0 or probability > 1
            for probability in probabilities.values()
        ):
            raise ValueError("answer probability outside [0,1]")
        total = sum(probabilities.values())
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"answer probabilities sum to {total}, expected 1")
        return probabilities

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float | None]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.transport.request(
            "POST",
            f"{self.base_url}/v1/systemone",
            payload=payload,
            headers=headers,
        )
        if not isinstance(response.body, dict):
            raise TypeError("CLM response body must be a JSON object")
        header = response.headers.get("X-CLM-Latency-Ms")
        return response.body, float(header) if header is not None else None

    def evaluate(self, state: Any, questions: Sequence[QuestionSpec]) -> ProviderResult:
        started = time.perf_counter()
        try:
            by_id = {question.id: question for question in questions}
            if len(by_id) != len(questions):
                raise ValueError("question ids must be unique")

            payload = {
                "state": state,
                "model": self.model,
                "temperature": self.temperature,
                "questions": {
                    question.id: self._question_payload(question) for question in questions
                },
            }
            response, server_latency_ms = self._post(payload)
            latency_ms = (time.perf_counter() - started) * 1000

            raw_answers = response.get("answers")
            if not isinstance(raw_answers, dict):
                raise TypeError("CLM response has no answers object")
            if set(raw_answers) != set(by_id):
                missing = sorted(set(by_id) - set(raw_answers))
                extra = sorted(set(raw_answers) - set(by_id))
                raise ValueError(f"CLM answer ids mismatch: missing={missing}, extra={extra}")

            decisions: dict[str, Decision] = {}
            for question_id, question in by_id.items():
                answer = raw_answers[question_id]
                if not isinstance(answer, dict):
                    raise TypeError(f"{question_id}: answer is not an object")
                if answer.get("type") != question.type:
                    raise ValueError(
                        f"{question_id}: answer type {answer.get('type')!r} "
                        f"does not match {question.type!r}"
                    )

                if question.type == "choice":
                    probabilities = self._probabilities(answer.get("probabilities"))
                    choice = str(answer["choice"])
                    if not isinstance(question.criteria, dict) or choice not in question.criteria:
                        raise ValueError(f"{question_id}: choice outside allowed criteria")
                    if set(probabilities) != set(question.criteria):
                        raise ValueError(f"{question_id}: probability labels do not match criteria")
                    decisions[question_id] = Decision(
                        question_id=question_id,
                        value=choice,
                        probabilities=probabilities,
                        confidence=float(answer["confidence"]),
                        predicted_probability=probabilities[choice],
                    )
                elif question.type == "noul":
                    probability = float(answer["noul"])
                    if not 0 <= probability <= 1:
                        raise ValueError(f"{question_id}: noul probability outside [0,1]")
                    decisions[question_id] = Decision(
                        question_id=question_id,
                        value=probability,
                        probabilities={"yes": probability, "no": 1.0 - probability},
                        confidence=abs(probability - 0.5) * 2,
                        predicted_probability=max(probability, 1.0 - probability),
                    )
                else:
                    probabilities = self._probabilities(answer.get("probabilities"))
                    decisions[question_id] = Decision(
                        question_id=question_id,
                        value=float(answer["score"]),
                        probabilities=probabilities,
                        confidence=float(answer["confidence"]),
                    )

            usage = response.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            resolved_model = str(response.get("model") or self.model)
            reported_model = self.benchmark_model_id or resolved_model
            return ProviderResult(
                provider=self.name,
                model=reported_model,
                answers=decisions,
                latency_ms=latency_ms,
                input_tokens=usage.get("input_tokens"),
                cached_input_tokens=None,
                output_tokens=usage.get("output_tokens"),
                estimated_cost_usd=0.0,
                raw={
                    "response": response,
                    "served_model": resolved_model,
                    "benchmark_model_id": self.benchmark_model_id,
                    "server_latency_ms": server_latency_ms,
                    "temperature": self.temperature,
                },
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary records failures
            return ProviderResult(
                provider=self.name,
                model=self.benchmark_model_id or self.model,
                answers={},
                latency_ms=(time.perf_counter() - started) * 1000,
                estimated_cost_usd=0.0,
                valid=False,
                error=f"{type(exc).__name__}: {exc}",
            )
