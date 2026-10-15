"""Response parsing and format extraction utilities for inference providers.

Provides robust JSON and LaTeX \\boxed{...} answer extraction for structured
capability tasks and mathematical reasoning models (such as Paradigma Limite).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


def extract_last_boxed_answer(text: str) -> str | None:
    """Extract the contents of the final \\boxed{...} expression from text.

    Correctly handles nested LaTeX braces within the \\boxed block.
    Returns None if no matching \\boxed block is found.
    """
    if not text:
        return None

    # Search backwards for \\boxed{ or boxed{
    search_terms = (r"\boxed{", "boxed{")
    idx = -1
    matched_term = ""
    for term in search_terms:
        pos = text.rfind(term)
        if pos > idx:
            idx = pos
            matched_term = term

    if idx == -1:
        return None

    start = idx + len(matched_term)
    depth = 1
    end = start

    while end < len(text) and depth > 0:
        char = text[end]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        end += 1

    if depth == 0:
        extracted = text[start : end - 1].strip()
        return extracted if extracted else None
    return None


def extract_json_from_text(text: str) -> Any | None:
    """Attempt to decode JSON directly or extract JSON from markdown/braces."""
    stripped = text.strip()
    if not stripped:
        return None

    # 1. Direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Outer braces { ... }
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(stripped[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def parse_chat_response_content(
    content: str,
    response_schema: Mapping[str, Any] | None = None,
    output_format: str | None = None,
) -> Any:
    """Parse model chat response into structured data.

    Tries standard JSON decoding first.
    If the model output is not raw JSON, attempts:
    - Markdown fenced JSON decoding
    - \\boxed{...} LaTeX extraction (especially for mathematical reasoning models)
    - Fallback single-field assignment if output is concise
    """
    # 1. If output_format is strictly boxed, check for boxed answer first
    if output_format == "boxed":
        boxed = extract_last_boxed_answer(content)
        if boxed is not None:
            field = _determine_target_field(response_schema)
            return {field: boxed}

    # 2. Try JSON decoding (raw, markdown, or substring)
    parsed = extract_json_from_text(content)
    if parsed is not None:
        return parsed

    # 3. Check for boxed answer (e.g. math models that don't output json)
    boxed = extract_last_boxed_answer(content)
    if boxed is not None:
        field = _determine_target_field(response_schema)
        return {field: boxed}

    # 4. Fallback for concise single-line text if a single field is expected
    target_field = _determine_target_field(response_schema)
    stripped = content.strip()
    if stripped and "\n" not in stripped and len(stripped) <= 128:
        return {target_field: stripped}

    if output_format == "boxed":
        raise ValueError(
            "No LaTeX \\boxed{...} answer found in model output. "
            f"Tail of output: {content[-120:]!r}"
        )

    # 5. Fall back to json.loads to raise a standard, informative JSONDecodeError
    return json.loads(content)


def _determine_target_field(response_schema: Mapping[str, Any] | None) -> str:
    """Determine the primary field name expected by the schema."""
    if not response_schema or not isinstance(response_schema, Mapping):
        return "answer"
    properties = response_schema.get("properties")
    if isinstance(properties, Mapping) and properties:
        required = response_schema.get("required")
        if isinstance(required, list) and required and required[0] in properties:
            return str(required[0])
        return str(next(iter(properties.keys())))
    return "answer"
