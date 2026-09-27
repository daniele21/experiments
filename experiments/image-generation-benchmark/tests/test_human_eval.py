from __future__ import annotations

from imagegen_bench.human_eval import build_blind_pair


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
