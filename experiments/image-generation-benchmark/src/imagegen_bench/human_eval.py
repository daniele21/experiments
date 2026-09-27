from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

PairwiseChoice = Literal["A", "B", "tie"]


@dataclass(frozen=True)
class BlindPair:
    pair_id: str
    prompt_id: str
    model_for_a: str
    model_for_b: str


@dataclass(frozen=True)
class PairwiseVote:
    pair_id: str
    prompt_id: str
    criterion: str
    choice: PairwiseChoice
    reviewer_id: str | None = None
    notes: str | None = None


def build_blind_pair(
    *,
    prompt_id: str,
    first_model: str,
    second_model: str,
    seed: int,
) -> BlindPair:
    if first_model == second_model:
        raise ValueError("blind comparison requires two different models")

    identity = f"{seed}:{prompt_id}:{first_model}:{second_model}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    swap = int(digest[-1], 16) % 2 == 1
    model_for_a, model_for_b = (
        (second_model, first_model) if swap else (first_model, second_model)
    )
    return BlindPair(
        pair_id=f"pair-{digest[:16]}",
        prompt_id=prompt_id,
        model_for_a=model_for_a,
        model_for_b=model_for_b,
    )
