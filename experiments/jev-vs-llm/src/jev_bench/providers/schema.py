from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jev_bench.models import QuestionSpec


def decision_response_schema(questions: Sequence[QuestionSpec]) -> dict[str, Any]:
    """Build a structured-output schema that binds each answer to its question."""
    answer_variants = [_answer_schema(question) for question in questions]
    item_schema: dict[str, Any]
    if answer_variants:
        item_schema = {"anyOf": answer_variants}
    else:
        item_schema = {}

    return {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": item_schema,
                "minItems": len(questions),
                "maxItems": len(questions),
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    }


def _answer_schema(question: QuestionSpec) -> dict[str, Any]:
    value_schema: dict[str, Any]
    if question.type == "choice":
        if not isinstance(question.criteria, dict) or not question.criteria:
            raise ValueError(f"Choice question {question.id!r} must define allowed criteria")
        value_schema = {"type": "string", "enum": list(question.criteria)}
    elif question.type in {"noul", "score"}:
        value_schema = {"type": "number"}
        if question.type == "noul":
            value_schema.update({"minimum": 0, "maximum": 1})
    else:
        raise ValueError(f"Unsupported question type {question.type!r}")

    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "const": question.id},
            "value": value_schema,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "selected_probability": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
        },
        "required": ["id", "value", "confidence", "selected_probability"],
        "additionalProperties": False,
    }
