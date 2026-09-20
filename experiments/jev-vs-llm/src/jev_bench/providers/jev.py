from __future__ import annotations

import os
import time
from typing import Any, Sequence

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from jev_bench.models import Decision, ProviderResult, QuestionSpec
from jev_bench.providers.base import DecisionProvider


class JevProvider(DecisionProvider):
    name = "jev"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("JEV_MODEL", "jev-latest")
        self.client = TypeSafeClient()

    @staticmethod
    def _question(q: QuestionSpec):
        if q.type == "choice":
            if not isinstance(q.criteria, dict):
                raise ValueError(f"Choice {q.id} requires dict criteria")
            return Choice(instructions=q.instructions, criteria=q.criteria)
        if q.type == "score":
            if not isinstance(q.criteria, list):
                raise ValueError(f"Score {q.id} requires list criteria")
            return Score(instructions=q.instructions, criteria=q.criteria)
        if q.type == "noul":
            return Noul(instructions=q.instructions)
        raise ValueError(f"Unsupported question type: {q.type}")

    def evaluate(self, state: Any, questions: Sequence[QuestionSpec]) -> ProviderResult:
        started = time.perf_counter()
        try:
            response = self.client.system_one(
                state=state,
                model=self.model,
                questions={q.id: self._question(q) for q in questions},
            )
            latency_ms = (time.perf_counter() - started) * 1000
            answers: dict[str, Decision] = {}
            for q in questions:
                answer = response.answers[q.id]
                if q.type == "choice":
                    answers[q.id] = Decision(
                        question_id=q.id,
                        value=answer.choice,
                        probabilities=dict(answer.probabilities),
                        confidence=float(answer.confidence),
                    )
                elif q.type == "score":
                    answers[q.id] = Decision(
                        question_id=q.id,
                        value=float(answer.score),
                        probabilities={str(k): float(v) for k, v in answer.probabilities.items()},
                        confidence=float(answer.confidence),
                    )
                else:
                    p = float(answer.noul)
                    answers[q.id] = Decision(
                        question_id=q.id,
                        value=p,
                        probabilities={"yes": p, "no": 1.0 - p},
                        confidence=abs(p - 0.5) * 2,
                    )
            usage = getattr(response, "usage", None)
            return ProviderResult(
                provider=self.name,
                model=getattr(response, "model", self.model),
                answers=answers,
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
