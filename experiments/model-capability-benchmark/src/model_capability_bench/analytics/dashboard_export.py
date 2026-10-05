from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from model_capability_bench.runner.comparison import paired_binary_comparison


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("DuckDB is required for dashboard export.") from exc
    return duckdb


def _decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _rows(connection: Any, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cursor = connection.execute(query, params or [])
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def export_dashboard_data(
    *,
    database_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    database_path = database_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    duckdb = _duckdb()
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        current = _rows(
            connection,
            """
            SELECT
                q.run_id,
                q.model_key,
                q.model_signature,
                q.benchmark_signature,
                q.execution_signature,
                q.capability_id,
                q.task_id,
                q.profile,
                q.sample_count,
                q.failure_count,
                q.primary_metric,
                q.primary_value,
                q.comparison_metric,
                q.practical_delta,
                q.completed_at_utc,
                r.git_commit,
                m.model_id,
                m.effective_model_id,
                m.runtime_key,
                m.provider_key,
                m.deployment
            FROM v_current_quality_results q
            JOIN models m
              ON m.run_id = q.run_id
             AND m.model_key = q.model_key
            JOIN runs r
              ON r.run_id = q.run_id
            ORDER BY q.capability_id, q.model_key
            """,
        )
        runs = _rows(
            connection,
            """
            SELECT *
            FROM runs
            ORDER BY completed_at_utc DESC, run_id DESC
            """,
        )
        capabilities = sorted({row["capability_id"] for row in current})
        models = {}
        for row in current:
            models[row["model_signature"]] = {
                "model_key": row["model_key"],
                "model_id": row["model_id"],
                "effective_model_id": row["effective_model_id"],
                "model_signature": row["model_signature"],
                "runtime_key": row["runtime_key"],
                "provider_key": row["provider_key"],
                "deployment": row["deployment"],
            }

        overview = {
            "schema_version": "1",
            "models": list(models.values()),
            "capabilities": capabilities,
            "cells": current,
            "runs": runs[:12],
        }
        overview_path = output_dir / "overview.json"
        overview_path.write_text(
            json.dumps(overview, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        capability_dir = output_dir / "capabilities"
        capability_dir.mkdir(parents=True, exist_ok=True)
        for capability_id in capabilities:
            cells = [row for row in current if row["capability_id"] == capability_id]
            benchmark_signatures = sorted(
                {row["benchmark_signature"] for row in cells}
            )
            payload = {
                "schema_version": "1",
                "capability_id": capability_id,
                "cells": cells,
                "benchmark_signatures": benchmark_signatures,
            }
            if len(benchmark_signatures) == 1:
                sig = benchmark_signatures[0]
                case_rows = _rows(
                    connection,
                    """
                    SELECT
                        c.run_id,
                        c.case_id,
                        c.attempt,
                        c.model_key,
                        c.model_signature,
                        c.sample_id,
                        c.dataset_id,
                        c.family,
                        c.difficulty,
                        c.challenge_type,
                        c.inference_valid,
                        c.evaluation_valid,
                        c.expected_json,
                        c.prediction_json,
                        c.latency_ms,
                        c.input_tokens,
                        c.output_tokens,
                        c.estimated_cost_usd,
                        cm.metric,
                        cm.value
                    FROM cases c
                    LEFT JOIN case_metrics cm
                      ON cm.run_id = c.run_id
                     AND cm.case_id = c.case_id
                     AND cm.attempt = c.attempt
                    WHERE c.capability_id = ?
                      AND c.benchmark_signature = ?
                      AND c.run_id IN (
                          SELECT run_id
                          FROM v_current_quality_results
                          WHERE capability_id = ?
                            AND benchmark_signature = ?
                      )
                    ORDER BY c.sample_id, c.model_key, cm.metric
                    """,
                    [capability_id, sig, capability_id, sig],
                )
                payload["cases"] = case_rows

                primary_by_model = {
                    row["model_key"]: row["primary_metric"]
                    for row in cells
                }
                primary_rows = [
                    row
                    for row in case_rows
                    if row["metric"] == primary_by_model.get(row["model_key"])
                    and row["value"] is not None
                ]
                grouped: dict[tuple[str, str], list[float]] = {}
                for row in primary_rows:
                    family = row["family"] or "unclassified"
                    grouped.setdefault(
                        (row["model_key"], family),
                        [],
                    ).append(float(row["value"]))
                payload["family_breakdown"] = [
                    {
                        "model_key": model_key,
                        "family": family,
                        "value": sum(values) / len(values),
                        "sample_count": len(values),
                    }
                    for (model_key, family), values in sorted(grouped.items())
                ]

                comparable_models = sorted(
                    {row["model_key"] for row in primary_rows}
                )
                disagreements: list[dict[str, Any]] = []
                if len(comparable_models) == 2:
                    model_a, model_b = comparable_models
                    by_sample: dict[str, dict[str, dict[str, Any]]] = {}
                    for row in primary_rows:
                        by_sample.setdefault(row["sample_id"], {})[
                            row["model_key"]
                        ] = row
                    for sample_id, pair in sorted(by_sample.items()):
                        if model_a not in pair or model_b not in pair:
                            continue
                        a = pair[model_a]
                        b = pair[model_b]
                        if not (
                            a["inference_valid"]
                            and a["evaluation_valid"]
                            and b["inference_valid"]
                            and b["evaluation_valid"]
                        ):
                            outcome = "pipeline_failure"
                        else:
                            a_ok = float(a["value"]) == 1.0
                            b_ok = float(b["value"]) == 1.0
                            if a_ok and b_ok:
                                outcome = "both_correct"
                            elif a_ok:
                                outcome = "a_only_correct"
                            elif b_ok:
                                outcome = "b_only_correct"
                            else:
                                outcome = "both_wrong"
                        disagreements.append(
                            {
                                "sample_id": sample_id,
                                "model_a": model_a,
                                "model_b": model_b,
                                "outcome": outcome,
                                "family": a["family"],
                                "difficulty": a["difficulty"],
                                "challenge_type": a["challenge_type"],
                                "dataset_id": a["dataset_id"],
                                "case_a": a["case_id"],
                                "case_b": b["case_id"],
                                "value_a": a["value"],
                                "value_b": b["value"],
                                "expected": _decode_json(a["expected_json"]),
                                "prediction_a": _decode_json(a["prediction_json"]),
                                "prediction_b": _decode_json(b["prediction_json"]),
                            }
                        )
                payload["disagreements"] = disagreements
                if len(comparable_models) == 2:
                    model_a, model_b = comparable_models

                    def comparison_evidence(
                        model_key: str,
                        primary_by_model: dict[str, str] = primary_by_model,
                        primary_rows: list[dict[str, Any]] = primary_rows,
                    ) -> list[dict[str, Any]]:
                        return [
                            {
                                "state": {
                                    "metadata": {
                                        "sample_id": row["sample_id"],
                                    }
                                },
                                "evaluation": {
                                    "record": {
                                        "metrics": [
                                            {
                                                "name": primary_by_model[model_key],
                                                "value": row["value"],
                                            }
                                        ]
                                    }
                                },
                            }
                            for row in primary_rows
                            if row["model_key"] == model_key
                        ]

                    payload["comparison"] = paired_binary_comparison(
                        comparison_evidence(model_a),
                        comparison_evidence(model_b),
                        metric_name=primary_by_model[model_a],
                        practical_delta=(
                            float(cells[0]["practical_delta"])
                            if cells
                            and cells[0].get("practical_delta") is not None
                            else None
                        ),
                    ) | {
                        "model_a": model_a,
                        "model_b": model_b,
                    }
            (capability_dir / f"{capability_id}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )

        model_dir = output_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_index: dict[str, str] = {}
        current_model_signatures = sorted(models)
        for model_signature in current_model_signatures:
            model_rows = _rows(
                connection,
                """
                SELECT
                    m.*,
                    r.completed_at_utc,
                    r.status AS run_status,
                    r.git_commit
                FROM models m
                JOIN runs r ON r.run_id = m.run_id
                WHERE m.model_signature = ?
                ORDER BY r.completed_at_utc DESC, m.run_id DESC
                """,
                [model_signature],
            )
            history = _rows(
                connection,
                """
                SELECT *
                FROM v_model_history
                WHERE model_signature = ?
                ORDER BY capability_id, completed_at_utc, run_id
                """,
                [model_signature],
            )
            current_cells = [
                row
                for row in current
                if row["model_signature"] == model_signature
            ]
            file_id = model_signature.split(":")[-1][:20]
            filename = f"{file_id}.json"
            model_index[model_signature] = f"models/{filename}"
            (model_dir / filename).write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "model_signature": model_signature,
                        "model": model_rows[0] if model_rows else None,
                        "current_cells": current_cells,
                        "history": history,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        run_dir = output_dir / "runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_index: dict[str, str] = {}
        lifecycle_prefixes = (
            "run.",
            "model.",
            "capability.",
            "projection.",
            "share.",
        )
        for run in runs:
            run_id = str(run["run_id"])
            run_index[run_id] = f"runs/{run_id}.json"
            run_models = _rows(
                connection,
                """
                SELECT *
                FROM models
                WHERE run_id = ?
                ORDER BY model_key
                """,
                [run_id],
            )
            run_cells = _rows(
                connection,
                """
                SELECT *
                FROM benchmark_cells
                WHERE run_id = ?
                ORDER BY model_key, capability_id
                """,
                [run_id],
            )
            lifecycle_events = _rows(
                connection,
                """
                SELECT *
                FROM events
                WHERE run_id = ?
                ORDER BY timestamp_utc, event_type
                """,
                [run_id],
            )
            lifecycle_events = [
                event
                for event in lifecycle_events
                if str(event["event_type"]).startswith(lifecycle_prefixes)
            ]
            failures = _rows(
                connection,
                """
                SELECT
                    event_type,
                    COALESCE(error_type, 'unknown') AS error_type,
                    COUNT(*) AS count,
                    MIN(timestamp_utc) AS first_at,
                    MAX(timestamp_utc) AS last_at
                FROM events
                WHERE run_id = ?
                  AND error_type IS NOT NULL
                GROUP BY event_type, error_type
                ORDER BY count DESC, event_type
                """,
                [run_id],
            )
            (run_dir / f"{run_id}.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "run": run,
                        "models": run_models,
                        "cells": run_cells,
                        "timeline": lifecycle_events,
                        "failure_summary": failures,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        index_path = output_dir / "index.json"
        index_path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "overview": "overview.json",
                    "capabilities": {
                        capability_id: f"capabilities/{capability_id}.json"
                        for capability_id in capabilities
                    },
                    "models": model_index,
                    "runs": run_index,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    finally:
        connection.close()

    return {
        "index": str(output_dir / "index.json"),
        "overview": str(output_dir / "overview.json"),
    }
