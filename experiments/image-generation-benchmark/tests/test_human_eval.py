from __future__ import annotations

from imagegen_bench.human_eval import build_blind_pair, build_blind_pairs


def test_blind_pair_assignment_is_deterministic_and_hides_order_bias() -> None:
    first = build_blind_pair(
        prompt_id="text-001",
        first_model="provider-a",
        second_model="provider-b",
        seed=42,
    )
    repeated = build_blind_pair(
        prompt_id="text-001",
        first_model="provider-a",
        second_model="provider-b",
        seed=42,
    )

    assert first == repeated
    assert {first.model_for_a, first.model_for_b} == {"provider-a", "provider-b"}
    assert first.pair_id.startswith("pair-")



def test_blind_pairs_cover_every_unique_model_pair_deterministically() -> None:
    pairs = build_blind_pairs(
        prompt_id="text-001",
        model_keys=["model-c", "model-a", "model-b"],
        seed=42,
    )
    repeated = build_blind_pairs(
        prompt_id="text-001",
        model_keys=["model-b", "model-c", "model-a"],
        seed=42,
    )

    assert pairs == repeated
    assert len(pairs) == 3
    compared = {
        frozenset((pair.model_for_a, pair.model_for_b))
        for pair in pairs
    }
    assert compared == {
        frozenset(("model-a", "model-b")),
        frozenset(("model-a", "model-c")),
        frozenset(("model-b", "model-c")),
    }
