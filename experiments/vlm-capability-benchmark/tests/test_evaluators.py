from __future__ import annotations

import pytest

from vlm_bench.evaluators import (
    BoundingBox,
    exact_match,
    numeric_match,
    point_distance,
    point_hits_box,
)


def test_text_and_numeric_evaluators_are_deterministic() -> None:
    assert exact_match("  Revenue   Growth ", "revenue growth")
    assert numeric_match(42.0, "42")
    assert numeric_match(42.0, "42.05", absolute_tolerance=0.1)
    assert not numeric_match(42.0, "43", absolute_tolerance=0.1)


def test_grounding_hit_and_distance() -> None:
    box = BoundingBox(0.7, 0.1, 0.9, 0.3)

    assert point_hits_box((0.8, 0.2), box)
    assert not point_hits_box((0.2, 0.2), box)
    assert point_distance((0.8, 0.2), box) == pytest.approx(0.0)


def test_invalid_box_is_rejected() -> None:
    with pytest.raises(ValueError, match="normalized"):
        BoundingBox(-0.1, 0.0, 0.5, 0.5)
