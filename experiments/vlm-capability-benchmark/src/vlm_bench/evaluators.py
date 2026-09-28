from __future__ import annotations

import math
import re
from dataclasses import dataclass

_WHITESPACE_RE = re.compile(r"\s+")


def normalized_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value).strip().casefold())


def exact_match(expected: object, prediction: object) -> bool:
    return normalized_text(expected) == normalized_text(prediction)


def numeric_match(
    expected: float,
    prediction: object,
    *,
    absolute_tolerance: float = 0.0,
) -> bool:
    if absolute_tolerance < 0:
        raise ValueError("absolute_tolerance must be >= 0")
    try:
        actual = float(str(prediction).strip().replace(",", ""))
    except (TypeError, ValueError):
        return False
    return math.isclose(actual, float(expected), rel_tol=0.0, abs_tol=absolute_tolerance)


@dataclass(frozen=True)
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("bounding-box coordinates must be normalized to [0, 1]")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("bounding box must have positive width and height")


def point_hits_box(point: tuple[float, float], box: BoundingBox) -> bool:
    x, y = point
    if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
        return False
    return box.x_min <= x <= box.x_max and box.y_min <= y <= box.y_max


def point_distance(
    point: tuple[float, float],
    target: BoundingBox,
) -> float:
    x, y = point
    center_x = (target.x_min + target.x_max) / 2
    center_y = (target.y_min + target.y_max) / 2
    return math.hypot(x - center_x, y - center_y)
