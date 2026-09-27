from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import floor
from typing import Any

from benchmark_core import CapabilityMetricSpec, CapabilitySpec


def _evaluation_record(item: Mapping[str, Any]) -> Mapping[str, Any]:
    record = item["evaluation"]["record"]
    if not isinstance(record, Mapping):
        raise TypeError("evaluation evidence record must be an object")
    return record


def _raw_record(item: Mapping[str, Any]) -> Mapping[str, Any]:
    record = item["raw"]["record"]
    if not isinstance(record, Mapping):
        raise TypeError("raw inference evidence record must be an object")
    return record


def _task_metric(item: Mapping[str, Any], name: str) -> Any:
    metrics = _evaluation_record(item).get("metrics") or []
    if not isinstance(metrics, list):
        raise TypeError("evaluation metrics must be a list")
    for metric in metrics:
        if isinstance(metric, Mapping) and metric.get("name") == name:
            return metric.get("value")
    return None


def _raw_field(item: Mapping[str, Any], field: str) -> Any:
    aliases = {
        "usage.input_tokens": "input_tokens",
        "usage.cached_input_tokens": "cached_input_tokens",
        "usage.output_tokens": "output_tokens",
    }
    key = aliases.get(field, field)
    return _raw_record(item).get(key)


def _numeric(values: Sequence[Any]) -> list[float]:
    return [
        float(value)
        for value in values
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _macro_f1(evidence: Sequence[Mapping[str, Any]]) -> float | None:
    expected = [_evaluation_record(item).get("expected") for item in evidence]
    predicted = [_evaluation_record(item).get("prediction") for item in evidence]
    labels = {
        value
        for value in [*expected, *predicted]
        if isinstance(value, str) and value
    }
    if not labels:
        return None

    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            exp == label and pred == label
            for exp, pred in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            exp != label and pred == label
            for exp, pred in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            exp == label and pred != label
            for exp, pred in zip(expected, predicted, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(
            0.0 if denominator == 0 else 2 * true_positive / denominator
        )
    return sum(scores) / len(scores)


def _oos_detection(
    evidence: Sequence[Mapping[str, Any]],
    oos_label: str,
) -> float | None:
    if not evidence:
        return None
    correct = 0
    for item in evidence:
        record = _evaluation_record(item)
        expected_oos = record.get("expected") == oos_label
        predicted_oos = record.get("prediction") == oos_label
        correct += expected_oos == predicted_oos
    return correct / len(evidence)


def _in_scope_accuracy(
    evidence: Sequence[Mapping[str, Any]],
    oos_label: str,
) -> float | None:
    in_scope = [
        item
        for item in evidence
        if _evaluation_record(item).get("expected") != oos_label
    ]
    if not in_scope:
        return None
    correct = sum(
        _evaluation_record(item).get("prediction")
        == _evaluation_record(item).get("expected")
        for item in in_scope
    )
    return correct / len(in_scope)


def _ece(
    evidence: Sequence[Mapping[str, Any]],
    *,
    confidence_metric: str,
    correctness_metric: str,
    bins: int,
) -> float | None:
    if bins <= 0:
        raise ValueError("ECE bins must be > 0")

    pairs: list[tuple[float, float]] = []
    for item in evidence:
        confidence = _task_metric(item, confidence_metric)
        correctness = _task_metric(item, correctness_metric)
        if (
            isinstance(confidence, int | float)
            and not isinstance(confidence, bool)
            and isinstance(correctness, int | float | bool)
        ):
            confidence_value = float(confidence)
            correctness_value = float(correctness)
            if 0 <= confidence_value <= 1 and 0 <= correctness_value <= 1:
                pairs.append((confidence_value, correctness_value))

    if not pairs:
        return None

    total = len(pairs)
    error = 0.0
    for bin_index in range(bins):
        lower = bin_index / bins
        upper = (bin_index + 1) / bins
        bucket = [
            pair
            for pair in pairs
            if lower <= pair[0] < upper
            or (bin_index == bins - 1 and pair[0] == 1.0)
        ]
        if not bucket:
            continue
        mean_confidence = sum(pair[0] for pair in bucket) / len(bucket)
        mean_correctness = sum(pair[1] for pair in bucket) / len(bucket)
        error += len(bucket) / total * abs(mean_confidence - mean_correctness)
    return error


def reduce_metric(
    metric: CapabilityMetricSpec,
    evidence: Sequence[Mapping[str, Any]],
) -> float | int | None:
    reducer = metric.reducer

    if reducer == "macro_f1":
        return _macro_f1(evidence)
    if reducer == "oos_detection":
        return _oos_detection(
            evidence,
            str(metric.options.get("oos_label") or "other"),
        )
    if reducer == "in_scope_accuracy":
        return _in_scope_accuracy(
            evidence,
            str(metric.options.get("oos_label") or "other"),
        )
    if reducer == "ece":
        return _ece(
            evidence,
            confidence_metric=str(
                metric.options.get("confidence_metric") or "confidence"
            ),
            correctness_metric=str(
                metric.options.get("correctness_metric") or "correct"
            ),
            bins=int(metric.options.get("bins") or 10),
        )

    field = metric.field or metric.name
    if metric.source == "task_metric":
        raw_values = [_task_metric(item, field) for item in evidence]
    elif metric.source == "inference":
        raw_values = [_raw_field(item, field) for item in evidence]
    else:
        raw_values = [
            _evaluation_record(item).get(field)
            for item in evidence
        ]

    if reducer == "invalid_rate":
        values = [
            bool(value)
            for value in raw_values
            if isinstance(value, bool)
        ]
        return (
            None
            if not values
            else sum(not value for value in values) / len(values)
        )

    values = _numeric(raw_values)
    if reducer == "mean" or reducer == "brier":
        return None if not values else sum(values) / len(values)
    if reducer == "sum":
        return None if not values else sum(values)
    if reducer == "rate":
        return None if not values else sum(bool(value) for value in values) / len(values)
    if reducer == "p50":
        return _percentile(values, 0.50)
    if reducer == "p95":
        return _percentile(values, 0.95)

    raise ValueError(f"Unsupported reducer: {reducer}")


def aggregate_capability(
    capability: CapabilitySpec,
    evidence: Sequence[Mapping[str, Any]],
    *,
    model_key: str,
    run_id: str,
    run_group: str,
    profile: str,
    failure_count: int = 0,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    datasets = sorted(
        {
            str(item["state"]["metadata"].get("dataset_id"))
            for item in evidence
        }
    )
    for metric in capability.metrics:
        records.append(
            {
                "run_id": run_id,
                "run_group": run_group,
                "model_key": model_key,
                "capability_id": capability.capability_id,
                "task_id": capability.task_id,
                "dataset_ids": datasets,
                "profile": profile,
                "metric": metric.name,
                "primary": metric.primary,
                "source": metric.source,
                "reducer": metric.reducer,
                "value": reduce_metric(metric, evidence),
                "sample_count": len(evidence),
                "failure_count": failure_count,
            }
        )
    return records
