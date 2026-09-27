from __future__ import annotations

from imagegen_bench.text_metrics import character_similarity, exact_text_match


def test_text_rendering_metrics_normalize_case_and_whitespace() -> None:
    assert exact_text_match("CAFFÈ CENTRALE", "  caffè   centrale ")
    assert character_similarity("20% OFF TODAY", "20% OFF TODAX") > 0.8
    assert character_similarity("ABC", "XYZ") < 0.5
