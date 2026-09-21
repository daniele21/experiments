from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from typing import Any

from openai import OpenAI

from jev_bench.costs import estimate_cost_usd
from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


class MiniCPMProvider(DecisionProvider):
    """MiniCPM API baseline through ModelBest's OpenAI-compatible endpoint.

    MiniCPM is intentionally treated as a remote API provider here, not as a
    Korgis/GGUF local model. The official MiniCPM API currently exposes
    OpenAI-compatible chat completions behind an API key.
    """

    name = "minicpm-api"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("MINICPM_MODEL", "MiniCPM-V-4.6-1B")
        api_key = os.getenv("MINICPM_API_KEY", "")
        if not api_key:
            raise ValueError("Set MINICPM_API_KEY before running MiniCPM API benchmarks")

        self.base_url = os.getenv("MINICPM_BASE_URL", "https://api.modelbest.cn/v1").rstrip("/")
        max_retries = int(os.getenv("BENCHMARK_MAX_RETRIES", "0"))
        timeout = float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60"))
        self.max_tokens = int(os.getenv("MINICPM_MAX_OUTPUT_TOKENS", "2048"))
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=api_key,
            max_retries=max_retries,
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
                    "Return one answer for every supplied question id exactly once. "
                    "Each answer must contain id, value, confidence and selected_probability. "
                    "For Choice, value must be exactly one supplied option. "
                    "For Noul, value is the probability of YES from 0 to 1. "
                    "For Score, value is numeric. confidence and selected_probability are 0-1."
                ),
                "state": state,
                "required_answer_ids": [question.id for question in questions],
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
                temperature=0.0,
                max_tokens=self.max_tokens,
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
                    if (
                        not isinstance(question.criteria, dict)
                        or str(value) not in question.criteria
                    ):
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
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers=decisions,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                cached_input_tokens=0,
                output_tokens=output_tokens,
                estimated_cost_usd=estimate_cost_usd(
                    provider=self.name,
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_input_tokens=0,
                ),
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
                valid=False,
                error=f"{type(exc).__name__}: {exc}",
            )
