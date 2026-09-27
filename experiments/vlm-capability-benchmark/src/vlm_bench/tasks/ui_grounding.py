from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark_core import (
    ContentPart,
    InferenceRequest,
    MediaRef,
    MetricResult,
    TaskResult,
    sha256_file,
)

from vlm_bench.datasets import DatasetCase
from vlm_bench.evaluators import exact_match, point_distance, point_hits_box


@dataclass(frozen=True)
class UIGroundingPrediction:
    target: str
    x: float
    y: float


def load_prompt_template(path: Path) -> str:
    template = path.read_text(encoding="utf-8")
    if "{question}" not in template:
        raise ValueError("UI grounding prompt template requires {question}")
    return template


def build_ui_grounding_request(
    case: DatasetCase,
    *,
    prompt_template: str,
) -> InferenceRequest:
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(case.asset_path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"unsupported UI asset extension: {case.asset_path.suffix}")

    media = MediaRef(
        media_id=case.sample_id,
        media_type="image",
        location=str(case.asset_path),
        mime_type=mime_type,
        sha256=sha256_file(case.asset_path),
    )
    return InferenceRequest(
        request_id=case.sample_id,
        content=(
            ContentPart(
                kind="text",
                text=prompt_template.format(question=case.question),
            ),
            ContentPart(kind="image", media=media),
        ),
        task_metadata={
            "task": case.task,
            "target_label": case.target_label,
        },
    )


def parse_ui_grounding_prediction(value: Any) -> UIGroundingPrediction:
    payload = json.loads(value) if isinstance(value, str) else value
    if not isinstance(payload, dict):
        raise ValueError("UI grounding prediction must be a JSON object")
    target = payload.get("target")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("UI grounding prediction requires target")
    try:
        x = float(payload["x"])
        y = float(payload["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("UI grounding prediction requires numeric x/y") from exc
    if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
        raise ValueError("UI grounding x/y must be normalized to [0, 1]")
    return UIGroundingPrediction(target=target.strip(), x=x, y=y)


def evaluate_ui_grounding(
    case: DatasetCase,
    prediction: Any,
) -> TaskResult:
    if case.target_box is None or case.target_label is None:
        raise ValueError(f"{case.sample_id}: grounding truth is incomplete")
    try:
        parsed = parse_ui_grounding_prediction(prediction)
    except ValueError as exc:
        return TaskResult(
            task_id=case.task,
            sample_id=case.sample_id,
            prediction=prediction,
            expected=case.expected,
            valid=False,
            error=str(exc),
        )

    point = (parsed.x, parsed.y)
    hit = point_hits_box(point, case.target_box)
    target_match = exact_match(case.target_label, parsed.target)
    return TaskResult(
        task_id=case.task,
        sample_id=case.sample_id,
        prediction={
            "target": parsed.target,
            "x": parsed.x,
            "y": parsed.y,
        },
        expected={
            "target": case.target_label,
            "box": [
                case.target_box.x_min,
                case.target_box.y_min,
                case.target_box.x_max,
                case.target_box.y_max,
            ],
        },
        metrics=(
            MetricResult(name="click_hit", value=hit, primary=True),
            MetricResult(name="target_match", value=target_match),
            MetricResult(
                name="point_distance",
                value=point_distance(point, case.target_box),
            ),
        ),
    )
