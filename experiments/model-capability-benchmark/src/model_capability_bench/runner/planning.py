from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from model_capability_bench.suite import CapabilitySuiteBundle


def plan_benchmark(
    bundle: CapabilitySuiteBundle,
    *,
    profile_id: str,
    capability_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    try:
        profile = bundle.profiles[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown profile {profile_id!r}") from exc

    selected = [
        capability
        for capability in bundle.resolved_capabilities
        if capability_ids is None
        or capability.spec.capability_id in set(capability_ids)
    ]
    if capability_ids is not None:
        requested = set(capability_ids)
        found = {item.spec.capability_id for item in selected}
        missing = sorted(requested - found)
        if missing:
            raise ValueError("Unknown capability IDs: " + ", ".join(missing))

    capabilities: list[dict[str, Any]] = []
    total_known_cases = 0
    all_counts_known = True
    target_local_seconds = 0.0
    hard_local_seconds = 0.0
    target_api_cost_usd = 0.0
    hard_api_cost_usd = 0.0

    for capability in selected:
        spec = capability.spec
        tier = spec.benchmark_tier(profile_id)
        dataset_cases: dict[str, int | None] = {}
        for dataset_id in spec.dataset_ids:
            fallback = profile.max_cases_for(dataset_id)
            dataset_cases[dataset_id] = (
                tier.max_cases_for(dataset_id, fallback=fallback)
                if tier is not None
                else fallback
            )

        known = [value for value in dataset_cases.values() if value is not None]
        if len(known) != len(dataset_cases):
            planned_cases = None
            all_counts_known = False
        else:
            planned_cases = sum(known)
            total_known_cases += planned_cases

        budget = {
            "target_local_seconds": (
                tier.target_local_seconds if tier is not None else None
            ),
            "hard_local_seconds": (
                tier.hard_local_seconds if tier is not None else None
            ),
            "target_api_cost_usd": (
                tier.target_api_cost_usd if tier is not None else None
            ),
            "hard_api_cost_usd": (
                tier.hard_api_cost_usd if tier is not None else None
            ),
        }
        target_local_seconds += float(budget["target_local_seconds"] or 0)
        hard_local_seconds += float(budget["hard_local_seconds"] or 0)
        target_api_cost_usd += float(budget["target_api_cost_usd"] or 0)
        hard_api_cost_usd += float(budget["hard_api_cost_usd"] or 0)

        capabilities.append(
            {
                "capability_id": spec.capability_id,
                "task_id": spec.task_id,
                "profile": profile_id,
                "dataset_cases": dataset_cases,
                "planned_cases": planned_cases,
                "selection_strategy": (
                    tier.selection.strategy if tier is not None else "profile"
                ),
                "practical_delta": spec.comparison.practical_delta,
                "comparison_metric": spec.comparison.metric,
                "budget": budget,
            }
        )

    return {
        "suite_id": bundle.suite.suite_id,
        "suite_version": bundle.suite.version,
        "profile": profile_id,
        "capabilities": capabilities,
        "planned_cases_per_model": (
            total_known_cases if all_counts_known else None
        ),
        "configured_budget_per_model": {
            "target_local_seconds": target_local_seconds or None,
            "hard_local_seconds": hard_local_seconds or None,
            "target_api_cost_usd": target_api_cost_usd or None,
            "hard_api_cost_usd": hard_api_cost_usd or None,
        },
        "semantics": (
            "Case counts are configured upper bounds. Runtime and API budgets are "
            "planning targets/ceilings; they are not model-specific estimates until "
            "a pilot measurement is available."
        ),
    }
