from __future__ import annotations

import json
import os
import time
from typing import Any, Sequence

from openai import OpenAI

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


class OpenAIProvider(DecisionProvider):
    """Structured-output LLM baseline.

    The LLM is asked to return a decision, confidence and probability distribution for
    every question. These probabilities are self-reported and should not be interpreted
    as equivalent to Jev's calibrated probabilities without empirical validation.
    """

    name = "llm-workflow"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "")
        if not self.model:
            raise ValueError("Set OPENAI_MODEL explicitly for reproducible benchmark runs")
        self.client = OpenAI()

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
                            "probabilities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "probability": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1,
                                        },
                                    },
                                    "required": ["label", "probability"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["id", "value", "confidence", "probabilities"],
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
                    "Return only the requested structured result. For Choice use one supplied option. "
                    "For Noul use a probability from 0 to 1 as value. For Score use a numeric position "
                    "on the supplied ordered scale. Give probabilities that sum approximately to 1."
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
                probs = {p["label"]: float(p["probability"]) for p in item["probabilities"]}
                decision = Decision(
                    question_id=qid,
                    value=item["value"],
                    probabilities=probs,
                    confidence=float(item["confidence"]),
                )
                q = by_id[qid]
                if q.type == "choice" and isinstance(q.criteria, dict):
                    if str(decision.value) not in q.criteria:
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
        except Exception as exc:
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
        self.client = OpenAI()

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
                },
                "required": ["action", "confidence"],
                "additionalProperties": False,
            }
            response = self.client.responses.create(
                model=self.model,
                input=json.dumps(
                    {
                        "task": "Apply the policy to the state and choose exactly one final action.",
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
                    )
                },
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                raw=response,
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name,
                model=self.model,
                answers={},
                latency_ms=(time.perf_counter() - started) * 1000,
                valid=False,
                error=f"{type(exc).__name__}: {exc}",
            )
