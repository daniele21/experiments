from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("DuckDB is required for dashboard export.") from exc
    return duckdb


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
                q.completed_at_utc,
                m.model_id,
                m.effective_model_id,
                m.runtime_key,
                m.provider_key,
                m.deployment
            FROM v_current_quality_results q
            JOIN models m
              ON m.run_id = q.run_id
             AND m.model_key = q.model_key
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
                    ORDER BY c.sample_id, c.model_key, cm.metric
                    """,
                    [capability_id, sig],
                )
                payload["cases"] = case_rows
            (capability_dir / f"{capability_id}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
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
