from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _rows(connection: Any, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _decode(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _parameter_value(
    changed_dimension: str | None,
    inference: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> Any:
    if not changed_dimension or changed_dimension == "factorial":
        return None
    namespace, key = changed_dimension.split(".", 1)
    source = inference if namespace == "inference" else runtime
    return source.get(key)


def build_sensitivity_payload(connection: Any) -> dict[str, Any]:
    rows = _rows(
        connection,
        """
        SELECT
            rc.run_id,
            rc.configuration_id,
            rc.sweep_id,
            rc.label,
            rc.changed_dimension,
            rc.is_baseline,
            rc.inference_json,
            rc.runtime_json,
            b.model_key,
            b.model_signature,
            b.capability_id,
            b.primary_metric,
            b.primary_value,
            b.sample_count,
            b.failure_count,
            r.completed_at_utc,
            perf.latency_p50_ms,
            perf.latency_mean_ms,
            perf.output_tokens_avg,
            res.process_rss_bytes_peak
        FROM run_configurations rc
        JOIN benchmark_cells b ON b.run_id = rc.run_id
        JOIN runs r ON r.run_id = rc.run_id
        LEFT JOIN (
            SELECT
                run_id,
                model_key,
                MEDIAN(latency_ms) AS latency_p50_ms,
                AVG(latency_ms) AS latency_mean_ms,
                AVG(output_tokens) AS output_tokens_avg
            FROM cases
            WHERE inference_valid
            GROUP BY run_id, model_key
        ) perf
          ON perf.run_id = b.run_id
         AND perf.model_key = b.model_key
        LEFT JOIN (
            SELECT
                run_id,
                model_key,
                MAX(process_rss_bytes_peak) AS process_rss_bytes_peak
            FROM resource_summaries
            GROUP BY run_id, model_key
        ) res
          ON res.run_id = b.run_id
         AND res.model_key = b.model_key
        WHERE rc.experiment_kind = 'sensitivity'
          AND b.status = 'COMPLETED'
        ORDER BY
            rc.sweep_id,
            b.model_key,
            b.capability_id,
            rc.is_baseline DESC,
            rc.changed_dimension,
            rc.label
        """,
    )

    points: list[dict[str, Any]] = []
    for row in rows:
        inference = _decode(row.pop("inference_json", None))
        runtime = _decode(row.pop("runtime_json", None))
        row["inference_config"] = inference
        row["runtime_config"] = runtime
        row["parameter_value"] = _parameter_value(
            row.get("changed_dimension"), inference, runtime
        )
        points.append(row)

    baselines: dict[tuple[str, str, str], dict[str, Any]] = {}
    for point in points:
        if point.get("is_baseline"):
            baselines[
                (
                    str(point.get("sweep_id")),
                    str(point.get("model_key")),
                    str(point.get("capability_id")),
                )
            ] = point

    for point in points:
        baseline = baselines.get(
            (
                str(point.get("sweep_id")),
                str(point.get("model_key")),
                str(point.get("capability_id")),
            )
        )
        if baseline is None:
            point["quality_delta_vs_baseline"] = None
            point["latency_delta_pct_vs_baseline"] = None
            point["rss_delta_pct_vs_baseline"] = None
            continue

        quality = point.get("primary_value")
        baseline_quality = baseline.get("primary_value")
        point["quality_delta_vs_baseline"] = (
            float(quality) - float(baseline_quality)
            if isinstance(quality, (int, float))
            and isinstance(baseline_quality, (int, float))
            else None
        )

        def delta_pct(key: str) -> float | None:
            value = point.get(key)
            base = baseline.get(key)
            if not isinstance(value, (int, float)):
                return None
            if not isinstance(base, (int, float)) or float(base) == 0:
                return None
            return (float(value) - float(base)) / float(base) * 100

        point["latency_delta_pct_vs_baseline"] = delta_pct("latency_p50_ms")
        point["rss_delta_pct_vs_baseline"] = delta_pct("process_rss_bytes_peak")

    return {
        "schema_version": "1",
        "points": points,
        "models": sorted({str(row["model_key"]) for row in points}),
        "sweeps": sorted({str(row["sweep_id"]) for row in points}),
        "capabilities": sorted({str(row["capability_id"]) for row in points}),
        "dimensions": sorted(
            {
                str(row["changed_dimension"])
                for row in points
                if row.get("changed_dimension")
            }
        ),
    }
