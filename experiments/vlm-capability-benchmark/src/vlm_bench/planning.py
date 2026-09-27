from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from benchmark_core import ConfigError, load_yaml_mapping, seeded_random, sha256_file

from vlm_bench.config import ResolvedVLMModel, resolve_vlm_models
from vlm_bench.datasets import DatasetCase, load_dataset_cases
from vlm_bench.tasks import load_prompt_template


@dataclass(frozen=True)
class VLMRunPlan:
    suite_id: str
    profile_id: str
    seed: int
    task_id: str
    evaluator_id: str
    prompt_path: Path
    prompt_sha256: str
    prompt_template: str
    models: tuple[ResolvedVLMModel, ...]
    cases: tuple[DatasetCase, ...]


def build_run_plan(
    root: Path,
    *,
    model_keys: Sequence[str],
    profile_id: str,
) -> VLMRunPlan:
    suite_payload = load_yaml_mapping(root / "suite.yaml", required=True)
    suite = suite_payload.get("suite")
    if not isinstance(suite, dict):
        raise ConfigError("suite.yaml requires a suite mapping")
    suite_id = str(suite.get("id", "")).strip()
    tasks = suite.get("tasks")
    if not suite_id or not isinstance(tasks, list) or len(tasks) != 1:
        raise ConfigError("VLM smoke suite requires exactly one configured task")

    task = tasks[0]
    if not isinstance(task, dict):
        raise ConfigError("suite task must be a mapping")
    task_id = str(task.get("id", "")).strip()
    dataset_rel = str(task.get("dataset", "")).strip()
    prompt_rel = str(task.get("prompt", "")).strip()
    evaluator_id = str(task.get("evaluator", "")).strip()
    if not all((task_id, dataset_rel, prompt_rel, evaluator_id)):
        raise ConfigError("task id, dataset, prompt and evaluator are required")

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
    max_cases = int(profile["max_cases_per_task"])
    if max_cases <= 0:
        raise ConfigError("max_cases_per_task must be > 0")

    cases = [
        case
        for case in load_dataset_cases(root / dataset_rel)
        if case.task == task_id
    ]
    if not cases:
        raise ConfigError(f"no dataset cases found for task {task_id!r}")
    rng = seeded_random(seed)
    rng.shuffle(cases)
    selected = tuple(cases[: min(max_cases, len(cases))])

    prompt_path = root / prompt_rel
    return VLMRunPlan(
        suite_id=suite_id,
        profile_id=profile_id,
        seed=seed,
        task_id=task_id,
        evaluator_id=evaluator_id,
        prompt_path=prompt_path,
        prompt_sha256=sha256_file(prompt_path),
        prompt_template=load_prompt_template(prompt_path),
        models=resolve_vlm_models(root, model_keys),
        cases=selected,
    )
