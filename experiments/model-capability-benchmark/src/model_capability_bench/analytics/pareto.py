from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def pareto_flags(
    points: Iterable[Mapping[str, Any]],
    *,
    x_key: str,
    y_key: str,
) -> dict[str, bool]:
    rows = [dict(point) for point in points]
    valid = [
        row
        for row in rows
        if _number(row.get(x_key)) is not None
        and _number(row.get(y_key)) is not None
    ]
    flags: dict[str, bool] = {}
    for point in rows:
        point_id = str(point["model_signature"])
        px = _number(point.get(x_key))
        py = _number(point.get(y_key))
        if px is None or py is None:
            flags[point_id] = False
            continue
        dominated = False
        for candidate in valid:
            if candidate is point:
                continue
            cx = _number(candidate.get(x_key))
            cy = _number(candidate.get(y_key))
            assert cx is not None and cy is not None
            if cx <= px and cy >= py and (cx < px or cy > py):
                dominated = True
                break
        flags[point_id] = not dominated
    return flags


def build_frontier_payload(
    model_summaries: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for summary in model_summaries:
        resources = summary.get("resource_summary")
        resources = resources if isinstance(resources, Mapping) else {}
        family = summary.get("family")
        parameters_b = _number(summary.get("parameters_b"))
        point = {
            "model_key": summary.get("model_key"),
            "model_signature": summary.get("model_signature"),
            "family": family,
            "parameters_b": parameters_b,
            "quantization": summary.get("quantization"),
            "artifact_size_bytes": summary.get("artifact_size_bytes"),
            "peak_rss_bytes": resources.get("process_rss_bytes_peak"),
            "latency_p50_ms": summary.get("latency_p50_ms"),
            "quality": summary.get("overall_quality_score"),
            "deployment": summary.get("deployment"),
            "compression_group": (
                f"{family}:{parameters_b:g}b"
                if family and parameters_b is not None
                else None
            ),
        }
        points.append(point)

    for x_key, flag_key in (
        ("parameters_b", "pareto_parameters"),
        ("artifact_size_bytes", "pareto_artifact_size"),
        ("peak_rss_bytes", "pareto_peak_rss"),
        ("latency_p50_ms", "pareto_latency"),
    ):
        flags = pareto_flags(points, x_key=x_key, y_key="quality")
        for point in points:
            point[flag_key] = flags.get(str(point["model_signature"]), False)

    return {
        "schema_version": "1",
        "points": points,
        "families": sorted(
            {str(point["family"]) for point in points if point.get("family")}
        ),
        "compression_groups": sorted(
            {
                str(point["compression_group"])
                for point in points
                if point.get("compression_group")
            }
        ),
    }
