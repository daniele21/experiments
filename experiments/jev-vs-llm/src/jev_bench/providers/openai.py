from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from typing import Any

from openai import OpenAI

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


class OpenAIProvider(DecisionProvider):
    """Low-output structured LLM baseline.

    The LLM returns only the selected value, a native/self-reported confidence score,
    and an estimated probability that the selected answer is correct. It is deliberately
    not asked to autoregressively emit the complete class distribution, which would
    unfairly inflate LLM latency relative to Jev's native probability distribution.
    """

    name = "llm-workflow"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "")
        if not self.model:
            raise ValueError("Set OPENAI_MODEL explicitly for reproducible benchmark runs")
        max_retries = int(os.getenv("BENCHMARK_MAX_RETRIES", "0"))
        timeout = float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60"))
        self.client = OpenAI(max_retries=max_retries, timeout=timeout)

    @staticmethod
    def _schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "value": {"type": ["string", "number"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "selected_probability": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": ["id", "value", "confidence", "selected_probability"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["answers"],
            "additionalProperties": False,
        }

    @staticmethod
    def _question_payload(q: QuestionSpec) -> dict[str, Any]:
        return {
            "id": q.id,
            "type": q.type,
            "instructions": q.instructions,
            "criteria": q.criteria,
        }

    def evaluate(self, state: Any, questions: Sequence[QuestionSpec]) -> ProviderResult:
        started = time.perf_counter()
        try:
            prompt = {
                "task": (
                    "Evaluate every question independently against the same state. "
                    "For Choice, value must be exactly one supplied option. "
                    "For Noul, value is the probability of YES from 0 to 1. "
                    "For Score, value is a numeric position on the supplied ordered scale. "
                    "confidence is your native 0-1 confidence in the decision. "
                    "selected_probability is your 0-1 estimate that the selected answer is correct. "
                    "Do not generate a full probability distribution."
                ),
                "state": state,
                "questions": [self._question_payload(q) for q in questions],
            }
            response = self.client.responses.create(
                model=self.model,
                input=json.dumps(prompt, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "decision_benchmark",
                        "strict": True,
                        "schema": self._schema(),
                    }
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            data = json.loads(response.output_text)
            by_id = {q.id: q for q in questions}
            decisions: dict[str, Decision] = {}
            valid = True
            errors: list[str] = []

            for item in data["answers"]:
                qid = item["id"]
                if qid not in by_id:
                    valid = False
                    errors.append(f"unexpected question id {qid}")
                    continue

                q = by_id[qid]
                value = item["value"]
                selected_probability = float(item["selected_probability"])
                if q.type == "noul":
                    p_yes = float(value)
                    selected_probability = max(p_yes, 1.0 - p_yes)

                decision = Decision(
                    question_id=qid,
                    value=value,
                    probabilities={},
                    confidence=float(item["confidence"]),
                    predicted_probability=selected_probability,
                )
                if (
                    q.type == "choice"
                    and isinstance(q.criteria, dict)
                    and str(decision.value) not in q.criteria
                ):
                    valid = False
                    errors.append(f"{qid}: value outside allowed choices")
                decisions[qid] = decision

            if set(decisions) != set(by_id):
                valid = False
                errors.append("missing question answers")

            usage = getattr(response, "usage", None)
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers=decisions,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                valid=valid,
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


class OpenAIMonolithicProvider:
    """LLM baseline that receives the whole policy and returns only the final action."""

    name = "llm-monolithic"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "")
        if not self.model:
            raise ValueError("Set OPENAI_MODEL explicitly for reproducible benchmark runs")
        max_retries = int(os.getenv("BENCHMARK_MAX_RETRIES", "0"))
        timeout = float(os.getenv("BENCHMARK_TIMEOUT_SECONDS", "60"))
        self.client = OpenAI(max_retries=max_retries, timeout=timeout)

    def decide(
        self,
        state: Any,
        policy: str,
        actions: Sequence[str],
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            schema = {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(actions)},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "selected_probability": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": ["action", "confidence", "selected_probability"],
                "additionalProperties": False,
            }
            response = self.client.responses.create(
                model=self.model,
                input=json.dumps(
                    {
                        "task": (
                            "Apply the policy to the state and choose exactly one final action. "
                            "Also estimate the probability that the selected action is correct."
                        ),
                        "policy": policy,
                        "state": state,
                        "allowed_actions": list(actions),
                    },
                    ensure_ascii=False,
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "final_action_benchmark",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            data = json.loads(response.output_text)
            usage = getattr(response, "usage", None)
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers={
                    "final_action": Decision(
                        question_id="final_action",
                        value=data["action"],
                        confidence=float(data["confidence"]),
                        predicted_probability=float(data["selected_probability"]),
                    )
                },
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
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
