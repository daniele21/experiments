from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def summarize_records(
    records: Sequence[Mapping[str, Any]],
    *,
    valid_field: str = "valid",
    correct_field: str = "correct",
    latency_field: str = "latency_ms",
) -> dict[str, int | float]:
    total = len(records)
    valid = sum(bool(record.get(valid_field)) for record in records)
    correct = sum(bool(record.get(correct_field)) for record in records)

    latencies: list[float] = []
    for record in records:
        value = record.get(latency_field)
        if value is None or value == "":
            continue
        latencies.append(float(value))

    return {
        "total_cases": total,
        "valid_cases": valid,
        "correct_cases": correct,
        "accuracy_pct": round(correct / total * 100 if total else 0.0, 1),
        "avg_latency_ms": round(
            sum(latencies) / len(latencies) if latencies else 0.0,
            1,
        ),
    }
