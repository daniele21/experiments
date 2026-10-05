from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from benchmark_core import DatasetLoadContext, Sample, seeded_random


def _matches(sample: Sample, match: Mapping[str, Any]) -> bool:
    return all(sample.metadata.get(key) == value for key, value in match.items())


def select_samples(
    samples: Sequence[Sample],
    *,
    dataset_id: str,
    context: DatasetLoadContext,
) -> tuple[Sample, ...]:
    available = list(samples)
    max_cases = context.max_cases_for(dataset_id)
    target = len(available) if max_cases is None else min(max_cases, len(available))
    selection = dict(context.selection)
    strategy = str(selection.get("strategy") or "profile")

    if strategy != "stratified" and target >= len(available):
        return tuple(available)

    if strategy == "fixed":
        return tuple(available[:target])

    rng = seeded_random(context.seed)
    if strategy == "profile":
        rng.shuffle(available)
        return tuple(available[:target])

    if strategy != "stratified":
        raise ValueError(f"Unsupported controlled selection strategy: {strategy}")

    quotas = selection.get("quotas") or []
    if not isinstance(quotas, list) or not quotas:
        raise ValueError("stratified selection requires a non-empty quotas list")

    selected: list[Sample] = []
    selected_ids: set[str] = set()
    requested = 0

    for index, raw_quota in enumerate(quotas):
        if not isinstance(raw_quota, Mapping):
            raise TypeError(f"selection quota {index} must be a mapping")
        match = raw_quota.get("match")
        if not isinstance(match, Mapping) or not match:
            raise TypeError(f"selection quota {index} match must be a mapping")
        count = int(raw_quota.get("count") or 0)
        if count <= 0:
            raise ValueError(f"selection quota {index} count must be > 0")
        requested += count

        candidates = [
            sample
            for sample in available
            if sample.sample_id not in selected_ids and _matches(sample, match)
        ]
        candidates.sort(key=lambda sample: sample.sample_id)
        rng.shuffle(candidates)
        if len(candidates) < count:
            raise ValueError(
                f"selection quota {index} for {dict(match)!r} requests {count} "
                f"cases but only {len(candidates)} are available"
            )
        for sample in candidates[:count]:
            selected.append(sample)
            selected_ids.add(sample.sample_id)

    if requested > target:
        raise ValueError(
            f"stratified quotas request {requested} cases but tier limit is {target}"
        )

    remaining = [
        sample for sample in available if sample.sample_id not in selected_ids
    ]
    remaining.sort(key=lambda sample: sample.sample_id)
    rng.shuffle(remaining)
    selected.extend(remaining[: target - len(selected)])
    return tuple(selected)
