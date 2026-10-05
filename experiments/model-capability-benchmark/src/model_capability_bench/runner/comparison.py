from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import comb
from random import Random
from typing import Any


def _evaluation_metric(item: Mapping[str, Any], metric_name: str) -> float | None:
    evaluation = item.get("evaluation")
    if not isinstance(evaluation, Mapping):
        return None
    record = evaluation.get("record")
    if not isinstance(record, Mapping):
        return None
    metrics = record.get("metrics")
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if isinstance(metric, Mapping) and metric.get("name") == metric_name:
            value = metric.get("value")
            if isinstance(value, bool):
                return float(value)
            if isinstance(value, int | float):
                return float(value)
    return None


def _sample_id(item: Mapping[str, Any]) -> str | None:
    state = item.get("state")
    if not isinstance(state, Mapping):
        return None
    metadata = state.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    value = metadata.get("sample_id")
    return str(value) if value is not None else None


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _mcnemar_exact(model_a_only: int, model_b_only: int) -> float | None:
    discordant = model_a_only + model_b_only
    if discordant == 0:
        return None
    tail = min(model_a_only, model_b_only)
    probability = sum(comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2.0 * probability)


def paired_binary_comparison(
    evidence_a: Sequence[Mapping[str, Any]],
    evidence_b: Sequence[Mapping[str, Any]],
    *,
    metric_name: str,
    practical_delta: float | None = None,
    bootstrap_samples: int = 2000,
    seed: int = 42,
) -> dict[str, Any]:
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be > 0")

    by_id_a = {
        sample_id: item
        for item in evidence_a
        if (sample_id := _sample_id(item)) is not None
    }
    by_id_b = {
        sample_id: item
        for item in evidence_b
        if (sample_id := _sample_id(item)) is not None
    }
    common_ids = sorted(set(by_id_a) & set(by_id_b))
    pairs: list[tuple[int, int]] = []
    for sample_id in common_ids:
        value_a = _evaluation_metric(by_id_a[sample_id], metric_name)
        value_b = _evaluation_metric(by_id_b[sample_id], metric_name)
        if value_a not in {0.0, 1.0} or value_b not in {0.0, 1.0}:
            continue
        pairs.append((int(value_a), int(value_b)))

    if not pairs:
        return {
            "metric": metric_name,
            "paired_count": 0,
            "delta_b_minus_a": None,
            "ci95_low": None,
            "ci95_high": None,
            "both_correct": 0,
            "model_a_only": 0,
            "model_b_only": 0,
            "both_wrong": 0,
            "mcnemar_exact_p": None,
            "practical_delta": practical_delta,
            "exceeds_practical_delta": None,
        }

    both_correct = sum(a == 1 and b == 1 for a, b in pairs)
    model_a_only = sum(a == 1 and b == 0 for a, b in pairs)
    model_b_only = sum(a == 0 and b == 1 for a, b in pairs)
    both_wrong = sum(a == 0 and b == 0 for a, b in pairs)
    differences = [b - a for a, b in pairs]
    delta = sum(differences) / len(differences)

    rng = Random(seed)
    bootstrap: list[float] = []
    for _ in range(bootstrap_samples):
        sampled = [differences[rng.randrange(len(differences))] for _ in differences]
        bootstrap.append(sum(sampled) / len(sampled))

    return {
        "metric": metric_name,
        "paired_count": len(pairs),
        "delta_b_minus_a": delta,
        "ci95_low": _percentile(bootstrap, 0.025),
        "ci95_high": _percentile(bootstrap, 0.975),
        "both_correct": both_correct,
        "model_a_only": model_a_only,
        "model_b_only": model_b_only,
        "both_wrong": both_wrong,
        "mcnemar_exact_p": _mcnemar_exact(model_a_only, model_b_only),
        "practical_delta": practical_delta,
        "exceeds_practical_delta": (
            abs(delta) >= practical_delta
            if practical_delta is not None
            else None
        ),
    }
