from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from benchmark_core import ConfigError, load_yaml_mapping, seeded_random

from imagegen_bench.config import ResolvedImageModel, resolve_image_models
from imagegen_bench.prompts import PromptCase, load_prompt_cases


@dataclass(frozen=True)
class ImageRunPlan:
    suite_id: str
    profile_id: str
    seed: int
    models: tuple[ResolvedImageModel, ...]
    prompts: tuple[PromptCase, ...]


def build_run_plan(
    root: Path,
    *,
    model_keys: Sequence[str],
    profile_id: str,
) -> ImageRunPlan:
    suite_payload = load_yaml_mapping(root / "suite.yaml", required=True)
    suite = suite_payload.get("suite")
    if not isinstance(suite, dict):
        raise ConfigError("suite.yaml requires a suite mapping")

    suite_id = str(suite.get("id", "")).strip()
    prompt_suite_path = str(suite.get("prompt_suite", "")).strip()
    if not suite_id or not prompt_suite_path:
        raise ConfigError("suite id and prompt_suite are required")

    profile_payload = load_yaml_mapping(
        root / "profiles" / f"{profile_id}.yaml",
        required=True,
    )
    profile = profile_payload.get("profile")
    if not isinstance(profile, dict):
        raise ConfigError(f"profile {profile_id!r} requires a profile mapping")
    if str(profile.get("id", "")).strip() != profile_id:
        raise ConfigError(f"profile id mismatch for {profile_id!r}")

    seed = int(profile["seed"])
    category_limits = profile.get("categories")
    if not isinstance(category_limits, dict) or not category_limits:
        raise ConfigError(f"profile {profile_id!r} requires category limits")

    all_prompts = load_prompt_cases(root / prompt_suite_path)
    by_category: dict[str, list[PromptCase]] = defaultdict(list)
    for prompt in all_prompts:
        by_category[prompt.category].append(prompt)

    rng = seeded_random(seed)
    selected: list[PromptCase] = []
    for category, raw_limit in category_limits.items():
        available = sorted(by_category.get(str(category), []), key=lambda item: item.prompt_id)
        limit = int(raw_limit)
        if limit <= 0:
            raise ConfigError(f"{profile_id}: category limit must be > 0 for {category}")
        if limit > len(available):
            raise ConfigError(
                f"{profile_id}: requested {limit} prompts for {category}, "
                f"only {len(available)} available"
            )
        indices = list(range(len(available)))
        rng.shuffle(indices)
        selected.extend(available[index] for index in sorted(indices[:limit]))

    return ImageRunPlan(
        suite_id=suite_id,
        profile_id=profile_id,
        seed=seed,
        models=resolve_image_models(root, model_keys),
        prompts=tuple(selected),
    )
