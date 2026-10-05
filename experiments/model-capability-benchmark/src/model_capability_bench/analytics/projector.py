from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from benchmark_core import read_jsonl_records, sha256_file

from model_capability_bench.observability.signatures import stable_signature


@dataclass(frozen=True)
class ProjectionSummary:
    database_path: str
    discovered_runs: int
    projected_runs: int
    skipped_runs: int
    quarantined_runs: int


def _duckdb():
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - dependency/configuration boundary
        raise RuntimeError(
            "DuckDB is required for analytics projection. Run uv sync first."
        ) from exc
    return duckdb


def _run_dirs(results_root: Path) -> list[Path]:
    runs_root = results_root / "runs"
    if not runs_root.is_dir():
        return []
    return sorted(
        {
            path.parent
            for path in runs_root.rglob("run_manifest.json")
            if path.is_file()
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "")


def _legacy_model_signature(model: Mapping[str, Any]) -> str:
    return stable_signature(
        "model",
        {
            "legacy": True,
            "model_key": model.get("model_key"),
            "model_id": model.get("model_id"),
            "effective_model_id": model.get("effective_model_id"),
            "runtime_key": model.get("runtime_key"),
        },
    )


def _legacy_execution_signature(model: Mapping[str, Any]) -> str:
    return stable_signature(
        "execution",
        {
            "legacy": True,
            "runtime_key": model.get("runtime_key"),
            "provider_key": model.get("provider_key"),
            "deployment": model.get("deployment"),
        },
    )


def _legacy_benchmark_signature(
    manifest: Mapping[str, Any],
    capability: Mapping[str, Any],
) -> str:
    suite = _mapping(manifest.get("suite"))
    return stable_signature(
        "benchmark",
        {
            "legacy": True,
            "suite_id": suite.get("suite_id"),
            "suite_version": suite.get("version"),
            "profile": suite.get("profile"),
            "seed": suite.get("seed"),
            "capability": capability,
        },
    )


def _signature_catalog(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = manifest.get("signatures")
    if isinstance(direct, Mapping):
        return direct
    run = _mapping(manifest.get("run"))
    metadata = _mapping(run.get("metadata"))
    signatures = metadata.get("signatures")
    return signatures if isinstance(signatures, Mapping) else {}


def _status(manifest: Mapping[str, Any]) -> str:
    run = _mapping(manifest.get("run"))
    planned = int(run.get("planned_cases") or 0)
    completed = int(run.get("completed_cases") or 0)
    failed = int(run.get("failed_cases") or 0)
    model_failures = int(run.get("model_failures") or 0)
    if model_failures > 0:
        return "PARTIAL" if completed > 0 else "FAILED"
    if failed > 0:
        return "PARTIAL"
    if planned > 0 and completed + int(run.get("skipped_cases") or 0) >= planned:
        return "COMPLETED"
    return "PARTIAL"


def _primary_metrics(capabilities: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for capability in capabilities:
        capability_id = _text(capability.get("capability_id"))
        for metric in capability.get("metrics") or []:
            if isinstance(metric, Mapping) and metric.get("primary") is True:
                result[capability_id] = _text(metric.get("name"))
                break
    return result


def _read_aggregates(run_dir: Path, run_id: str) -> list[Mapping[str, Any]]:
    return [
        item
        for item in read_jsonl_records(run_dir / "aggregates.jsonl")
        if _text(item.get("run_id")) == run_id
    ]


def _read_report_indices(run_dir: Path, run_id: str) -> list[Mapping[str, Any]]:
    return [
        item
        for item in read_jsonl_records(run_dir / "report_index.jsonl")
        if _text(item.get("run_id")) == run_id
    ]


def _read_case_records(
    run_dir: Path,
    run_id: str,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    raw = {}
    for item in read_jsonl_records(run_dir / "raw.jsonl"):
        record = _mapping(item.get("record"))
        if _text(record.get("run_id")) != run_id:
            continue
        key = (_text(item.get("case_id")), int(item.get("attempt") or 0))
        raw[key] = item

    evaluations = {}
    for item in read_jsonl_records(run_dir / "evaluation.jsonl"):
        record = _mapping(item.get("record"))
        if _text(record.get("run_id")) != run_id:
            continue
        key = (_text(item.get("case_id")), int(item.get("attempt") or 0))
        evaluations[key] = item

    return [
        (raw[key], evaluations[key])
        for key in sorted(set(raw).intersection(evaluations))
    ]


def _create_schema(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id VARCHAR PRIMARY KEY,
            run_group VARCHAR,
            source_dir VARCHAR,
            created_at_utc VARCHAR,
            completed_at_utc VARCHAR,
            status VARCHAR,
            suite_id VARCHAR,
            suite_version VARCHAR,
            profile VARCHAR,
            seed BIGINT,
            git_commit VARCHAR,
            manifest_checksum VARCHAR,
            integrity_state VARCHAR
        );

        CREATE TABLE IF NOT EXISTS models (
            run_id VARCHAR,
            model_key VARCHAR,
            model_id VARCHAR,
            effective_model_id VARCHAR,
            model_signature VARCHAR,
            execution_signature VARCHAR,
            runtime_key VARCHAR,
            provider_key VARCHAR,
            deployment VARCHAR,
            quantization VARCHAR,
            artifact_format VARCHAR,
            PRIMARY KEY (run_id, model_key)
        );

        CREATE TABLE IF NOT EXISTS benchmark_cells (
            run_id VARCHAR,
            model_key VARCHAR,
            model_signature VARCHAR,
            benchmark_signature VARCHAR,
            execution_signature VARCHAR,
            capability_id VARCHAR,
            task_id VARCHAR,
            profile VARCHAR,
            sample_count BIGINT,
            failure_count BIGINT,
            status VARCHAR,
            primary_metric VARCHAR,
            primary_value DOUBLE,
            comparison_metric VARCHAR,
            practical_delta DOUBLE,
            completed_at_utc VARCHAR,
            PRIMARY KEY (run_id, model_key, capability_id)
        );

        CREATE TABLE IF NOT EXISTS aggregates (
            run_id VARCHAR,
            model_key VARCHAR,
            capability_id VARCHAR,
            metric VARCHAR,
            value DOUBLE,
            sample_count BIGINT,
            failure_count BIGINT,
            primary BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS cases (
            run_id VARCHAR,
            case_id VARCHAR,
            attempt BIGINT,
            model_key VARCHAR,
            model_signature VARCHAR,
            benchmark_signature VARCHAR,
            execution_signature VARCHAR,
            capability_id VARCHAR,
            dataset_id VARCHAR,
            sample_id VARCHAR,
            family VARCHAR,
            difficulty VARCHAR,
            challenge_type VARCHAR,
            inference_valid BOOLEAN,
            evaluation_valid BOOLEAN,
            expected_json VARCHAR,
            prediction_json VARCHAR,
            latency_ms DOUBLE,
            input_tokens BIGINT,
            cached_input_tokens BIGINT,
            output_tokens BIGINT,
            estimated_cost_usd DOUBLE,
            error_kind VARCHAR,
            raw_file VARCHAR,
            evaluation_file VARCHAR,
            PRIMARY KEY (run_id, case_id, attempt)
        );

        CREATE TABLE IF NOT EXISTS case_metrics (
            run_id VARCHAR,
            case_id VARCHAR,
            attempt BIGINT,
            metric VARCHAR,
            value DOUBLE,
            primary BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS events (
            run_id VARCHAR,
            event_id VARCHAR,
            event_type VARCHAR,
            timestamp_utc VARCHAR,
            model_key VARCHAR,
            capability_id VARCHAR,
            dataset_id VARCHAR,
            sample_id VARCHAR,
            case_id VARCHAR,
            attempt BIGINT,
            status VARCHAR,
            duration_ms DOUBLE,
            error_type VARCHAR,
            error_message VARCHAR,
            metadata_json VARCHAR
        );

        CREATE OR REPLACE VIEW v_current_quality_results AS
        SELECT * EXCLUDE (rn)
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY model_signature, benchmark_signature, capability_id
                    ORDER BY completed_at_utc DESC, run_id DESC
                ) AS rn
            FROM benchmark_cells
            WHERE status = 'COMPLETED'
        )
        WHERE rn = 1;

        CREATE OR REPLACE VIEW v_current_performance_results AS
        SELECT * EXCLUDE (rn)
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY model_signature, benchmark_signature,
                                 execution_signature, capability_id
                    ORDER BY completed_at_utc DESC, run_id DESC
                ) AS rn
            FROM benchmark_cells
            WHERE status = 'COMPLETED'
        )
        WHERE rn = 1;

        CREATE OR REPLACE VIEW v_model_history AS
        SELECT
            b.*,
            CASE
                WHEN q.run_id = b.run_id THEN 'CURRENT'
                WHEN b.status = 'COMPLETED' THEN 'HISTORICAL'
                ELSE 'PARTIAL'
            END AS result_state
        FROM benchmark_cells b
        LEFT JOIN v_current_quality_results q
          ON q.run_id = b.run_id
         AND q.model_signature = b.model_signature
         AND q.benchmark_signature = b.benchmark_signature
         AND q.capability_id = b.capability_id;
        """
    )


def _clear_run(connection: Any, run_id: str) -> None:
    for table in (
        "events",
        "case_metrics",
        "cases",
        "aggregates",
        "benchmark_cells",
        "models",
        "runs",
    ):
        connection.execute(f"DELETE FROM {table} WHERE run_id = ?", [run_id])


def _project_one(connection: Any, run_dir: Path) -> tuple[bool, str]:
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run = _mapping(manifest.get("run"))
    suite = _mapping(manifest.get("suite"))
    run_id = _text(run.get("run_id"))
    if not run_id:
        return False, "INVALID"

    capabilities = [
        item for item in manifest.get("capabilities") or [] if isinstance(item, Mapping)
    ]
    models = [
        item for item in manifest.get("models") or [] if isinstance(item, Mapping)
    ]
    signatures = _signature_catalog(manifest)
    model_sigs = _mapping(signatures.get("models"))
    execution_sigs = _mapping(signatures.get("executions"))
    benchmark_sigs = _mapping(signatures.get("benchmarks"))

    status = _status(manifest)
    created_at = _text(manifest.get("created_at_utc"))
    completed_at = created_at
    primary_by_capability = _primary_metrics(capabilities)
    capability_by_id = {
        _text(item.get("capability_id")): item for item in capabilities
    }

    _clear_run(connection, run_id)
    connection.execute(
        """
        INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            _text(run.get("run_group")),
            str(run_dir),
            created_at,
            completed_at,
            status,
            _text(suite.get("suite_id")),
            _text(suite.get("version")),
            _text(suite.get("profile")),
            int(suite.get("seed") or 0),
            _text(_mapping(run.get("metadata")).get("git_commit")) or None,
            sha256_file(manifest_path),
            "VALID",
        ],
    )

    model_sig_by_key: dict[str, str] = {}
    execution_sig_by_key: dict[str, str] = {}
    for model in models:
        key = _text(model.get("model_key"))
        model_sig = _text(model_sigs.get(key)) or _legacy_model_signature(model)
        execution_sig = (
            _text(execution_sigs.get(key)) or _legacy_execution_signature(model)
        )
        model_sig_by_key[key] = model_sig
        execution_sig_by_key[key] = execution_sig
        connection.execute(
            "INSERT INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                key,
                _text(model.get("model_id")),
                _text(model.get("effective_model_id")),
                model_sig,
                execution_sig,
                _text(model.get("runtime_key")),
                _text(model.get("provider_key")),
                _text(model.get("deployment")),
                _text(model.get("quantization")) or None,
                _text(model.get("artifact_format")) or None,
            ],
        )

    aggregate_records = _read_aggregates(run_dir, run_id)
    for aggregate in aggregate_records:
        value = aggregate.get("value")
        connection.execute(
            "INSERT INTO aggregates VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                _text(aggregate.get("model_key")),
                _text(aggregate.get("capability_id")),
                _text(aggregate.get("metric")),
                float(value) if isinstance(value, (int, float)) else None,
                int(aggregate.get("sample_count") or 0),
                int(aggregate.get("failure_count") or 0),
                bool(aggregate.get("primary")),
            ],
        )

    report_indices = _read_report_indices(run_dir, run_id)
    index_by_cell = {
        (_text(item.get("model_key")), _text(item.get("capability_id"))): item
        for item in report_indices
    }
    for model in models:
        model_key = _text(model.get("model_key"))
        for capability_id, capability in capability_by_id.items():
            index = index_by_cell.get((model_key, capability_id), {})
            primary_metric = primary_by_capability.get(capability_id, "")
            primary_records = [
                item
                for item in aggregate_records
                if _text(item.get("model_key")) == model_key
                and _text(item.get("capability_id")) == capability_id
                and _text(item.get("metric")) == primary_metric
            ]
            primary = primary_records[-1] if primary_records else {}
            benchmark_sig = (
                _text(benchmark_sigs.get(capability_id))
                or _legacy_benchmark_signature(manifest, capability)
            )
            cell_status = (
                "COMPLETED"
                if status == "COMPLETED"
                and primary
                and int(index.get("failure_count") or 0) == 0
                else "PARTIAL"
            )
            value = primary.get("value")
            connection.execute(
                """
                INSERT INTO benchmark_cells
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    model_key,
                    model_sig_by_key[model_key],
                    benchmark_sig,
                    execution_sig_by_key[model_key],
                    capability_id,
                    _text(capability.get("task_id")),
                    _text(suite.get("profile")),
                    int(primary.get("sample_count") or len(index.get("cases") or [])),
                    int(index.get("failure_count") or primary.get("failure_count") or 0),
                    cell_status,
                    primary_metric,
                    float(value) if isinstance(value, (int, float)) else None,
                    _text(_mapping(capability.get("comparison")).get("metric"))
                    or None,
                    (
                        float(_mapping(capability.get("comparison")).get("practical_delta"))
                        if isinstance(
                            _mapping(capability.get("comparison")).get("practical_delta"),
                            (int, float),
                        )
                        else None
                    ),
                    completed_at,
                ],
            )

    partial_cells = connection.execute(
        """
        SELECT COUNT(*)
        FROM benchmark_cells
        WHERE run_id = ?
          AND status <> 'COMPLETED'
        """,
        [run_id],
    ).fetchone()[0]
    if partial_cells:
        connection.execute(
            "UPDATE runs SET status = 'PARTIAL' WHERE run_id = ?",
            [run_id],
        )

    for raw_item, evaluation_item in _read_case_records(run_dir, run_id):
        raw_record = _mapping(raw_item.get("record"))
        evaluation_record = _mapping(evaluation_item.get("record"))
        metadata = _mapping(raw_item.get("metadata"))
        model_key = _text(metadata.get("model_key"))
        capability_id = _text(metadata.get("capability_id"))
        capability = capability_by_id.get(capability_id, {})
        benchmark_sig = (
            _text(metadata.get("benchmark_signature"))
            or _text(benchmark_sigs.get(capability_id))
            or _legacy_benchmark_signature(manifest, capability)
        )
        model_sig = (
            _text(metadata.get("model_signature"))
            or model_sig_by_key.get(model_key, "")
        )
        execution_sig = (
            _text(metadata.get("execution_signature"))
            or execution_sig_by_key.get(model_key, "")
        )
        case_id = _text(raw_item.get("case_id"))
        attempt = int(raw_item.get("attempt") or 0)
        connection.execute(
            """
            INSERT INTO cases VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                run_id,
                case_id,
                attempt,
                model_key,
                model_sig,
                benchmark_sig,
                execution_sig,
                capability_id,
                _text(metadata.get("dataset_id")),
                _text(metadata.get("sample_id")),
                _text(metadata.get("case_family")) or None,
                _text(metadata.get("difficulty")) or None,
                _text(metadata.get("challenge_type")) or None,
                bool(raw_record.get("valid")),
                bool(evaluation_record.get("valid")),
                json.dumps(
                    evaluation_record.get("expected"),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                json.dumps(
                    evaluation_record.get("prediction"),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                float(raw_record.get("latency_ms") or 0.0),
                raw_record.get("input_tokens"),
                raw_record.get("cached_input_tokens"),
                raw_record.get("output_tokens"),
                raw_record.get("estimated_cost_usd"),
                _text(raw_record.get("error_kind")) or None,
                "raw.jsonl",
                "evaluation.jsonl",
            ],
        )
        for metric in evaluation_record.get("metrics") or []:
            if not isinstance(metric, Mapping):
                continue
            value = metric.get("value")
            connection.execute(
                "INSERT INTO case_metrics VALUES (?, ?, ?, ?, ?, ?)",
                [
                    run_id,
                    case_id,
                    attempt,
                    _text(metric.get("name")),
                    float(value)
                    if isinstance(value, (int, float, bool))
                    else None,
                    bool(metric.get("primary")),
                ],
            )

    for event in read_jsonl_records(run_dir / "events.jsonl"):
        metadata = _mapping(event.get("metadata"))
        event_run_id = _text(event.get("run_id") or metadata.get("run_id"))
        if event_run_id != run_id:
            continue
        connection.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                _text(event.get("event_id")) or None,
                _text(event.get("event_type") or event.get("event")),
                _text(event.get("timestamp_utc")),
                _text(event.get("model_key") or metadata.get("model_key")) or None,
                _text(event.get("capability_id") or metadata.get("capability_id")) or None,
                _text(event.get("dataset_id") or metadata.get("dataset_id")) or None,
                _text(event.get("sample_id") or metadata.get("sample_id")) or None,
                _text(event.get("case_id") or metadata.get("case_id")) or None,
                event.get("attempt") or metadata.get("attempt"),
                _text(event.get("status")) or None,
                event.get("duration_ms"),
                _text(event.get("error_type")) or None,
                _text(event.get("error_message")) or None,
                json.dumps(metadata, sort_keys=True),
            ],
        )

    return True, "VALID"


def project_results(
    *,
    results_root: Path,
    database_path: Path | None = None,
    rebuild: bool = False,
    run_dirs: tuple[Path, ...] | None = None,
) -> ProjectionSummary:
    results_root = results_root.resolve()
    database_path = (
        database_path.resolve()
        if database_path is not None
        else results_root / "analytics" / "benchmark.duckdb"
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if rebuild and database_path.exists():
        database_path.unlink()

    duckdb = _duckdb()
    connection = duckdb.connect(str(database_path))
    discovered = (
        sorted({path.resolve() for path in run_dirs})
        if run_dirs is not None
        else _run_dirs(results_root)
    )
    projected = 0
    quarantined = 0
    skipped = 0
    try:
        _create_schema(connection)
        for run_dir in discovered:
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.is_file():
                quarantined += 1
                continue
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )
                run_id = _text(_mapping(manifest.get("run")).get("run_id"))
                manifest_checksum = sha256_file(manifest_path)
                existing = (
                    connection.execute(
                        """
                        SELECT manifest_checksum
                        FROM runs
                        WHERE run_id = ?
                        """,
                        [run_id],
                    ).fetchone()
                    if run_id
                    else None
                )
                if (
                    not rebuild
                    and existing is not None
                    and existing[0] == manifest_checksum
                ):
                    skipped += 1
                    continue
                ok, _ = _project_one(connection, run_dir)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                quarantined += 1
                continue
            if ok:
                projected += 1
            else:
                skipped += 1
        connection.execute("CHECKPOINT")
    finally:
        connection.close()

    manifest_path = database_path.parent / "projection_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "database": str(database_path),
                "discovered_runs": len(discovered),
                "projected_runs": projected,
                "skipped_runs": skipped,
                "quarantined_runs": quarantined,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return ProjectionSummary(
        database_path=str(database_path),
        discovered_runs=len(discovered),
        projected_runs=projected,
        skipped_runs=skipped,
        quarantined_runs=quarantined,
    )
