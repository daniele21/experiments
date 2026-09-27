from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class PromptSuiteError(ValueError):
    pass


@dataclass(frozen=True)
class PromptCase:
    prompt_id: str
    category: str
    difficulty: str
    prompt: str
    expectations: Mapping[str, Any] = field(default_factory=dict)
    negative_constraints: tuple[str, ...] = ()
    evaluators: tuple[str, ...] = ()


def _required_text(raw: Mapping[str, Any], key: str, prompt_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PromptSuiteError(f"{prompt_id}: {key} must be non-empty text")
    return value


def load_prompt_cases(path: str | Path) -> tuple[PromptCase, ...]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("prompts"), list):
        raise PromptSuiteError("prompt suite root must contain a prompts list")

    seen: set[str] = set()
    cases: list[PromptCase] = []
    for index, raw in enumerate(payload["prompts"]):
        if not isinstance(raw, dict):
            raise PromptSuiteError(f"prompt {index} must be a mapping")
        prompt_id = _required_text(raw, "prompt_id", f"prompt-{index}")
        if prompt_id in seen:
            raise PromptSuiteError(f"duplicate prompt_id: {prompt_id}")
        seen.add(prompt_id)

        expectations = raw.get("expectations") or {}
        if not isinstance(expectations, dict):
            raise PromptSuiteError(f"{prompt_id}: expectations must be a mapping")

        negative = raw.get("negative_constraints") or []
        evaluators = raw.get("evaluators") or []
        if not isinstance(negative, list) or not all(isinstance(x, str) for x in negative):
            raise PromptSuiteError(f"{prompt_id}: negative_constraints must be text list")
        if not isinstance(evaluators, list) or not all(isinstance(x, str) for x in evaluators):
            raise PromptSuiteError(f"{prompt_id}: evaluators must be text list")

        cases.append(
            PromptCase(
                prompt_id=prompt_id,
                category=_required_text(raw, "category", prompt_id),
                difficulty=_required_text(raw, "difficulty", prompt_id),
                prompt=_required_text(raw, "prompt", prompt_id),
                expectations=expectations,
                negative_constraints=tuple(negative),
                evaluators=tuple(evaluators),
            )
        )

    return tuple(cases)
