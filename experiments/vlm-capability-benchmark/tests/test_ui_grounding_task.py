from __future__ import annotations

from pathlib import Path

from vlm_bench.datasets import load_dataset_cases
from vlm_bench.tasks import (
    build_ui_grounding_request,
    evaluate_ui_grounding,
    load_prompt_template,
    parse_ui_grounding_prediction,
)


ROOT = Path(__file__).parents[1]


def test_ui_grounding_request_uses_versioned_prompt_and_image() -> None:
    case = load_dataset_cases(ROOT / "datasets" / "controlled_ui_grounding.yaml")[0]
    template = load_prompt_template(ROOT / "prompts" / "ui_grounding_v1.txt")

    request = build_ui_grounding_request(case, prompt_template=template)

    assert request.request_id == case.sample_id
    assert len(request.content) == 2
    assert request.content[0].kind == "text"
    assert case.question in request.content[0].text
    assert request.content[1].kind == "image"
    assert request.content[1].media is not None
    assert request.content[1].media.sha256


def test_ui_grounding_evaluation_keeps_metrics_separate() -> None:
    case = load_dataset_cases(ROOT / "datasets" / "controlled_ui_grounding.yaml")[0]

    result = evaluate_ui_grounding(
        case,
        '{"target":"Create project","x":0.86,"y":0.12}',
    )

    metrics = {metric.name: metric.value for metric in result.metrics}
    assert result.valid
    assert metrics["click_hit"] is True
    assert metrics["target_match"] is True
    assert metrics["point_distance"] >= 0.0


def test_ui_grounding_invalid_json_is_typed_as_invalid_task_result() -> None:
    case = load_dataset_cases(ROOT / "datasets" / "controlled_ui_grounding.yaml")[0]

    result = evaluate_ui_grounding(case, "not-json")

    assert not result.valid
    assert result.error
    assert result.metrics == ()


def test_prediction_coordinates_must_be_normalized() -> None:
    try:
        parse_ui_grounding_prediction('{"target":"Create project","x":2,"y":0.1}')
    except ValueError as exc:
        assert "normalized" in str(exc)
    else:
        raise AssertionError("out-of-range coordinates must be rejected")
