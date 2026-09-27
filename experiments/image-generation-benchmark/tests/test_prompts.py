from __future__ import annotations

from collections import Counter
from pathlib import Path

from imagegen_bench.prompts import load_prompt_cases


def test_core_prompt_suite_is_balanced_and_unique() -> None:
    path = Path(__file__).parents[1] / "prompt_suites" / "core_v1.yaml"

    prompts = load_prompt_cases(path)
    counts = Counter(prompt.category for prompt in prompts)

    assert len(prompts) == 20
    assert len({prompt.prompt_id for prompt in prompts}) == 20
    assert counts == {
        "text_rendering": 5,
        "compositional": 5,
        "photorealism": 5,
        "design": 5,
    }


def test_compositional_prompts_have_structured_expectations() -> None:
    path = Path(__file__).parents[1] / "prompt_suites" / "core_v1.yaml"

    prompts = load_prompt_cases(path)
    compositional = [prompt for prompt in prompts if prompt.category == "compositional"]

    assert all("objects" in prompt.expectations for prompt in compositional)
    assert all("constraint_check" in prompt.evaluators for prompt in compositional)
