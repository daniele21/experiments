from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any
import yaml

QUALITY_POLICY = {
    "quality_policy_id": "core-quality-v1",
    "label": "Equal-weight capability quality",
    "aggregation": "mean_normalized_primary_metric",
    "coverage_requirement": "complete",
    "normalization": "higher-is-better unit metrics mapped to 0-100",
}


def _load_models_yaml_config() -> dict[str, Any]:
    for path in (Path("models.yaml"), Path(__file__).resolve().parents[3] / "models.yaml"):
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data.get("models") or {}
            except Exception:
                pass
    return {}


def _rows(
    connection: Any,
    query: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    cursor = connection.execute(query, params or [])
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _selected_cohorts(
    current: list[dict[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    by_capability: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in current:
        by_capability[str(row["capability_id"])][
            str(row["benchmark_signature"])
        ].append(row)

    selected: dict[str, str] = {}
    for capability_id, signatures in by_capability.items():
        ranked = sorted(
            signatures.items(),
            key=lambda item: (
                len({str(row["model_signature"]) for row in item[1]}),
                max(str(row.get("completed_at_utc") or "") for row in item[1]),
                item[0],
            ),
            reverse=True,
        )
        if ranked:
            selected[capability_id] = ranked[0][0]

    by_cap_model: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in current:
        by_cap_model[(str(row["capability_id"]), str(row["model_key"]))].append(row)

    filtered: list[dict[str, Any]] = []
    for (cap_id, _), rows in by_cap_model.items():
        canonical_sig = selected.get(cap_id)
        matching = [
            r for r in rows if str(r.get("benchmark_signature")) == canonical_sig
        ]
        if matching:
            filtered.append(matching[0])
        else:
            latest = max(rows, key=lambda r: str(r.get("completed_at_utc") or ""))
            filtered.append(latest)
    return selected, filtered


def _pareto_membership(
    rows: list[dict[str, Any]],
    *,
    x_key: str,
    y_key: str,
) -> set[str]:
    eligible = [
        row
        for row in rows
        if _number(row.get(x_key)) is not None
        and _number(row.get(y_key)) is not None
    ]
    frontier: set[str] = set()
    for candidate in eligible:
        candidate_x = float(candidate[x_key])
        candidate_y = float(candidate[y_key])
        dominated = False
        for other in eligible:
            if other is candidate:
                continue
            other_x = float(other[x_key])
            other_y = float(other[y_key])
            if (
                other_x <= candidate_x
                and other_y >= candidate_y
                and (other_x < candidate_x or other_y > candidate_y)
            ):
                dominated = True
                break
        if not dominated:
            frontier.add(str(candidate["model_signature"]))
    return frontier


def _annotate_pareto(
    rows: list[dict[str, Any]],
    *,
    y_key: str,
) -> None:
    latency_frontier = _pareto_membership(
        rows,
        x_key="latency_p50_ms",
        y_key=y_key,
    )
    cost_frontier = _pareto_membership(
        [
            row
            for row in rows
            if row.get("provider_cost_status") == "complete"
        ],
        x_key="provider_cost_per_1k_cases_usd",
        y_key=y_key,
    )
    for row in rows:
        signature = str(row["model_signature"])
        row["observed_quality_latency_pareto"] = signature in latency_frontier
        row["known_provider_cost_quality_pareto"] = signature in cost_frontier


def _load_case_evidence(
    connection: Any,
    cells: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, int, str], float]]:
    run_ids = sorted({str(row["run_id"]) for row in cells})
    if not run_ids:
        return [], {}
    placeholders = ", ".join("?" for _ in run_ids)
    cases = _rows(
        connection,
        f"""
        SELECT
            run_id,
            case_id,
            attempt,
            model_key,
            model_signature,
            execution_signature,
            capability_id,
            dataset_id,
            sample_id,
            family,
            difficulty,
            challenge_type,
            inference_valid,
            evaluation_valid,
            latency_ms,
            input_tokens,
            cached_input_tokens,
            output_tokens,
            estimated_cost_usd
        FROM cases
        WHERE run_id IN ({placeholders})
        """,
        run_ids,
    )
    metrics = _rows(
        connection,
        f"""
        SELECT run_id, case_id, attempt, metric, value
        FROM case_metrics
        WHERE run_id IN ({placeholders})
        """,
        run_ids,
    )
    metric_map = {
        (
            str(row["run_id"]),
            str(row["case_id"]),
            int(row["attempt"]),
            str(row["metric"]),
        ): float(row["value"])
        for row in metrics
        if _number(row.get("value")) is not None
    }
    cell_keys = {
        (
            str(row["run_id"]),
            str(row["model_key"]),
            str(row["capability_id"]),
        )
        for row in cells
    }
    cases = [
        row
        for row in cases
        if (
            str(row["run_id"]),
            str(row["model_key"]),
            str(row["capability_id"]),
        )
        in cell_keys
    ]
    return cases, metric_map


def _load_pricing(
    connection: Any,
    cells: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    run_ids = sorted({str(row["run_id"]) for row in cells})
    if not run_ids:
        return {}
    exists = connection.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = 'run_pricing'
        """
    ).fetchone()[0]
    if not exists:
        return {}
    placeholders = ", ".join("?" for _ in run_ids)
    rows = _rows(
        connection,
        f"""
        SELECT run_id, currency, as_of, processing, prices_json
        FROM run_pricing
        WHERE run_id IN ({placeholders})
        """,
        run_ids,
    )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            prices = json.loads(str(row.get("prices_json") or "{}"))
        except json.JSONDecodeError:
            prices = {}
        result[str(row["run_id"])] = {
            "currency": row.get("currency"),
            "as_of": row.get("as_of"),
            "processing": row.get("processing"),
            "prices_per_million_tokens": prices if isinstance(prices, dict) else {},
        }
    return result


def _price_entry_for_model(
    run_pricing: dict[str, dict[str, Any]],
    *,
    run_id: str,
    model_key: str,
    model_id: Any,
    effective_model_id: Any,
    provider_key: Any,
) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    snapshot = run_pricing.get(run_id)
    if not snapshot:
        return None
    prices = snapshot.get("prices_per_million_tokens")
    if not isinstance(prices, dict):
        return None

    for candidate in (model_key, model_id, effective_model_id):
        if not candidate:
            continue
        entry = prices.get(str(candidate))
        if isinstance(entry, dict) and str(entry.get("match") or "exact") == "exact":
            return snapshot, entry, str(candidate)

    for price_key, entry in prices.items():
        if not isinstance(entry, dict):
            continue
        match_type = str(entry.get("match") or "")
        if match_type == "prefix":
            for candidate in (model_key, model_id, effective_model_id):
                if candidate and str(candidate).startswith(str(price_key)):
                    return snapshot, entry, str(price_key)
        elif match_type == "provider" and str(price_key) == str(provider_key):
            return snapshot, entry, str(price_key)
    return None


def _pricing_for_model(
    run_pricing: dict[str, dict[str, Any]],
    *,
    run_id: str,
    model_key: str,
    model_id: Any,
    effective_model_id: Any,
    provider_key: Any,
) -> dict[str, Any] | None:
    resolved = _price_entry_for_model(
        run_pricing,
        run_id=run_id,
        model_key=model_key,
        model_id=model_id,
        effective_model_id=effective_model_id,
        provider_key=provider_key,
    )
    if resolved is None:
        return None
    snapshot, entry, price_key = resolved
    return {
        "price_key": price_key,
        "source": entry.get("source"),
        "source_url": entry.get("source_url"),
        "currency": snapshot.get("currency"),
        "as_of": snapshot.get("as_of"),
        "processing": snapshot.get("processing"),
    }


def _estimate_case_cost_from_frozen_pricing(
    case: dict[str, Any],
    cell: dict[str, Any],
    run_pricing: dict[str, dict[str, Any]],
) -> float | None:
    if _number(case.get("estimated_cost_usd")) is not None:
        return float(case["estimated_cost_usd"])

    resolved = _price_entry_for_model(
        run_pricing,
        run_id=str(case["run_id"]),
        model_key=str(case["model_key"]),
        model_id=cell.get("model_id"),
        effective_model_id=cell.get("effective_model_id"),
        provider_key=cell.get("provider_key"),
    )
    if resolved is None:
        return None
    _, entry, _ = resolved
    try:
        input_price = float(entry["input"])
        output_price = float(entry["output"])
        cached_price = float(entry.get("cached_input", entry["input"]))
    except (KeyError, TypeError, ValueError):
        return None

    input_tokens = case.get("input_tokens")
    output_tokens = case.get("output_tokens")
    if input_tokens is None and output_tokens is None:
        return None

    input_total = max(int(input_tokens or 0), 0)
    output_total = max(int(output_tokens or 0), 0)
    cached = min(max(int(case.get("cached_input_tokens") or 0), 0), input_total)
    uncached = input_total - cached
    return (
        uncached * input_price
        + cached * cached_price
        + output_total * output_price
    ) / 1_000_000


def _backfill_case_costs(
    cases: list[dict[str, Any]],
    cell_by_key: dict[tuple[str, str, str], dict[str, Any]],
    run_pricing: dict[str, dict[str, Any]],
) -> int:
    reconstructed = 0
    for case in cases:
        if _number(case.get("estimated_cost_usd")) is not None:
            continue
        cell = cell_by_key.get(
            (
                str(case["run_id"]),
                str(case["model_key"]),
                str(case["capability_id"]),
            )
        )
        if cell is None:
            continue
        estimated = _estimate_case_cost_from_frozen_pricing(
            case,
            cell,
            run_pricing,
        )
        if estimated is None:
            continue
        case["estimated_cost_usd"] = estimated
        reconstructed += 1
    return reconstructed

def _load_environments(
    connection: Any,
    cells: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    run_ids = sorted({str(row["run_id"]) for row in cells})
    if not run_ids:
        return {}
    placeholders = ", ".join("?" for _ in run_ids)
    rows = _rows(
        connection,
        f"""
        SELECT *
        FROM execution_environments
        WHERE run_id IN ({placeholders})
        """,
        run_ids,
    )
    return {
        (str(row["run_id"]), str(row["execution_signature"])): row
        for row in rows
    }


def _load_run_parameters(
    connection: Any,
    cells: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    run_ids = sorted({str(row["run_id"]) for row in cells})
    if not run_ids:
        return {}
    placeholders = ", ".join("?" for _ in run_ids)
    rows = _rows(
        connection,
        f"""
        SELECT run_id, profile, seed, source_dir
        FROM runs
        WHERE run_id IN ({placeholders})
        """,
        run_ids,
    )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = str(row["run_id"])
        source_dir = row.get("source_dir")
        gen_params: dict[str, Any] = {}
        if source_dir:
            env_file = Path(source_dir) / "environment.json"
            if env_file.is_file():
                try:
                    env_data = json.loads(env_file.read_text(encoding="utf-8"))
                    gen_params = (env_data.get("parameters") or {}).get("generation") or {}
                except Exception:
                    pass
        result[run_id] = {
            "profile": row.get("profile"),
            "seed": row.get("seed"),
            "generation": gen_params,
        }
    return result


def _aggregate_case_metrics(
    cases: list[dict[str, Any]],
    *,
    deployment: str,
) -> dict[str, Any]:
    latency = [
        float(row["latency_ms"])
        for row in cases
        if _number(row.get("latency_ms")) is not None
    ]
    costs = [
        float(row["estimated_cost_usd"])
        for row in cases
        if _number(row.get("estimated_cost_usd")) is not None
    ]
    priced_case_count = len(costs)
    total_case_count = len(cases)
    if deployment == "local":
        provider_cost_status = "local_not_applicable"
    elif total_case_count == 0 or priced_case_count == 0:
        provider_cost_status = "unavailable"
    elif priced_case_count == total_case_count:
        provider_cost_status = "complete"
    else:
        provider_cost_status = "partial"
    provider_cost_known = provider_cost_status in {"complete", "partial"}
    provider_cost_coverage_rate = (
        priced_case_count / total_case_count
        if total_case_count
        else None
    )
    invalid = sum(
        1
        for row in cases
        if not bool(row.get("inference_valid"))
        or not bool(row.get("evaluation_valid"))
    )
    input_tokens = [
        int(row["input_tokens"])
        for row in cases
        if isinstance(row.get("input_tokens"), int)
    ]
    output_tokens = [
        int(row["output_tokens"])
        for row in cases
        if isinstance(row.get("output_tokens"), int)
    ]
    observed_total_cost = sum(costs) if provider_cost_known else None
    mean_priced_cost = _mean(costs) if provider_cost_known else None
    return {
        "observed_case_count": len(cases),
        "latency_p50_ms": _quantile(latency, 0.50),
        "latency_p95_ms": _quantile(latency, 0.95),
        "latency_mean_ms": _mean(latency),
        "provider_cost_status": provider_cost_status,
        "provider_cost_known": provider_cost_known,
        "provider_cost_priced_cases": priced_case_count,
        "provider_cost_total_cases": total_case_count,
        "provider_cost_coverage_rate": provider_cost_coverage_rate,
        "provider_cost_observed_total_usd": observed_total_cost,
        "provider_cost_total_usd": (
            observed_total_cost
            if provider_cost_status == "complete"
            else None
        ),
        "provider_cost_per_case_usd": mean_priced_cost,
        "provider_cost_per_1k_cases_usd": (
            mean_priced_cost * 1000
            if mean_priced_cost is not None
            else None
        ),
        "input_tokens_total": sum(input_tokens) if input_tokens else None,
        "output_tokens_total": sum(output_tokens) if output_tokens else None,
        "failure_count": invalid,
        "failure_rate": invalid / len(cases) if cases else None,
    }


def build_decision_overview(
    connection: Any,
    current: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_signatures, cells = _selected_cohorts(current)
    cases, metric_map = _load_case_evidence(connection, cells)
    environments = _load_environments(connection, cells)
    run_pricing = _load_pricing(connection, cells)
    run_parameters = _load_run_parameters(connection, cells)
    models_config = _load_models_yaml_config()

    cell_by_key = {
        (
            str(row["run_id"]),
            str(row["model_key"]),
            str(row["capability_id"]),
        ): row
        for row in cells
    }
    _backfill_case_costs(cases, cell_by_key, run_pricing)
    cases_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cases_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    cases_by_dataset: dict[
        tuple[str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for case in cases:
        model_key = str(case["model_key"])
        capability_id = str(case["capability_id"])
        dataset_id = str(case["dataset_id"])
        cases_by_model[model_key].append(case)
        cases_by_cell[(model_key, capability_id)].append(case)
        cases_by_dataset[(model_key, capability_id, dataset_id)].append(case)

    model_meta: dict[str, dict[str, Any]] = {}
    model_cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        model_key = str(cell["model_key"])
        model_cells[model_key].append(cell)
        if model_key not in model_meta:
            cfg = (
                models_config.get(model_key)
                or models_config.get(str(cell.get("effective_model_id") or ""))
                or models_config.get(str(cell.get("model_id") or ""))
                or {}
            )
            artifact = cfg.get("artifact") or {}
            model_meta[model_key] = {
                "model_key": model_key,
                "model_signature": str(cell["model_signature"]),
                "model_id": cell.get("model_id"),
                "effective_model_id": cell.get("effective_model_id"),
                "runtime_key": cell.get("runtime_key"),
                "provider_key": cell.get("provider_key"),
                "deployment": cell.get("deployment"),
                "family": cfg.get("family"),
                "parameters_b": cfg.get("parameters_b"),
                "quantization": cell.get("quantization") or artifact.get("quantization"),
                "artifact_format": cell.get("artifact_format") or artifact.get("format"),
                "tags": cfg.get("tags") or [],
            }

    capability_count = len(selected_signatures)
    dataset_ids = sorted({str(row["dataset_id"]) for row in cases})
    model_summaries: list[dict[str, Any]] = []

    for model_key, meta in sorted(model_meta.items()):
        model_current_cells = model_cells[model_key]
        capability_values = [
            float(row["primary_value"]) * 100.0
            for row in model_current_cells
            if _number(row.get("primary_value")) is not None
        ]
        covered_capabilities = len(
            {
                str(row["capability_id"])
                for row in model_current_cells
                if _number(row.get("primary_value")) is not None
            }
        )
        model_dataset_ids = {
            str(case["dataset_id"]) for case in cases_by_model[model_key]
        }
        complete = capability_count > 0 and covered_capabilities == capability_count
        quality_score = _mean(capability_values) if capability_values else None

        observed = _aggregate_case_metrics(
            cases_by_model[model_key],
            deployment=str(meta.get("deployment") or ""),
        )
        execution_pairs = sorted(
            {
                (str(row["run_id"]), str(row["execution_signature"]))
                for row in model_current_cells
            }
        )
        latest_cell = max(
            model_current_cells,
            key=lambda row: str(row.get("completed_at_utc") or ""),
        )
        latest_environment = environments.get(
            (
                str(latest_cell["run_id"]),
                str(latest_cell["execution_signature"]),
            )
        )
        latest_run_id = str(latest_cell["run_id"])
        run_info = run_parameters.get(latest_run_id) or {}
        if not run_info.get("generation"):
            for cell_row in model_current_cells:
                alt_info = run_parameters.get(str(cell_row["run_id"]))
                if alt_info and alt_info.get("generation"):
                    run_info = alt_info
                    break

        resource_rows = [
            row["resource_summary"]
            for row in model_current_cells
            if isinstance(row.get("resource_summary"), dict)
        ]
        cpu_values = [
            float(row["process_cpu_percent_avg"])
            for row in resource_rows
            if _number(row.get("process_cpu_percent_avg")) is not None
        ]
        rss_values = [
            float(row["process_rss_bytes_peak"])
            for row in resource_rows
            if _number(row.get("process_rss_bytes_peak")) is not None
        ]

        pricing = _pricing_for_model(
            run_pricing,
            run_id=str(latest_cell["run_id"]),
            model_key=model_key,
            model_id=meta.get("model_id"),
            effective_model_id=meta.get("effective_model_id"),
            provider_key=meta.get("provider_key"),
        )
        model_summaries.append(
            {
                **meta,
                "quality_policy_id": QUALITY_POLICY["quality_policy_id"],
                "overall_quality_score": quality_score,
                "quality_coverage_capabilities": covered_capabilities,
                "quality_total_capabilities": capability_count,
                "quality_coverage_datasets": len(model_dataset_ids),
                "quality_total_datasets": len(dataset_ids),
                "quality_coverage_complete": complete,
                **observed,
                "provider_cost_pricing": pricing,
                "execution_count": len(execution_pairs),
                "execution_environment": latest_environment,
                "execution_profile": run_info.get("profile"),
                "generation_parameters": run_info.get("generation") or {},
                "resource_summary": {
                    "process_cpu_percent_avg": _mean(cpu_values),
                    "process_rss_bytes_peak": max(rss_values) if rss_values else None,
                },
                "latest_completed_at_utc": latest_cell.get("completed_at_utc"),
                "current_run_ids": sorted(
                    {str(row["run_id"]) for row in model_current_cells}
                ),
            }
        )

    _annotate_pareto(model_summaries, y_key="overall_quality_score")

    capability_summaries: list[dict[str, Any]] = []
    for cell in cells:
        model_key = str(cell["model_key"])
        capability_id = str(cell["capability_id"])
        observed = _aggregate_case_metrics(
            cases_by_cell[(model_key, capability_id)],
            deployment=str(cell.get("deployment") or ""),
        )
        capability_pricing = _pricing_for_model(
            run_pricing,
            run_id=str(cell["run_id"]),
            model_key=model_key,
            model_id=cell.get("model_id"),
            effective_model_id=cell.get("effective_model_id"),
            provider_key=cell.get("provider_key"),
        )
        capability_summaries.append(
            {
                "run_id": cell["run_id"],
                "model_key": model_key,
                "model_signature": cell["model_signature"],
                "capability_id": capability_id,
                "benchmark_signature": cell["benchmark_signature"],
                "execution_signature": cell["execution_signature"],
                "primary_metric": cell["primary_metric"],
                "primary_value": cell["primary_value"],
                "normalized_quality_score": (
                    float(cell["primary_value"]) * 100.0
                    if _number(cell.get("primary_value")) is not None
                    else None
                ),
                "sample_count": cell["sample_count"],
                "failure_count": cell["failure_count"],
                **observed,
                "provider_cost_pricing": capability_pricing,
            }
        )

    capability_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in capability_summaries:
        capability_groups[str(row["capability_id"])].append(row)
    for rows in capability_groups.values():
        _annotate_pareto(rows, y_key="normalized_quality_score")

    dataset_summaries: list[dict[str, Any]] = []
    for (model_key, capability_id, dataset_id), dataset_cases in sorted(
        cases_by_dataset.items()
    ):
        sample_cell = cell_by_key[
            (
                str(dataset_cases[0]["run_id"]),
                model_key,
                capability_id,
            )
        ]
        primary_metric = str(sample_cell["primary_metric"])
        comparison_metric = str(sample_cell.get("comparison_metric") or "")
        resolved_metric = primary_metric
        values: list[float] = []
        for case in dataset_cases:
            value = metric_map.get(
                (
                    str(case["run_id"]),
                    str(case["case_id"]),
                    int(case["attempt"]),
                    primary_metric,
                )
            )
            if value is not None:
                values.append(value)

        if not values and dataset_cases:
            candidate_metrics = tuple(
                filter(
                    None,
                    (
                        comparison_metric,
                        "oos_correct",
                        "correct",
                        "accuracy",
                        "exact_match",
                    ),
                )
            )
            first_case = dataset_cases[0]
            for candidate in candidate_metrics:
                probe_key = (
                    str(first_case["run_id"]),
                    str(first_case["case_id"]),
                    int(first_case["attempt"]),
                    candidate,
                )
                if probe_key in metric_map:
                    resolved_metric = candidate
                    values = [
                        metric_map[k]
                        for c in dataset_cases
                        if (
                            k := (
                                str(c["run_id"]),
                                str(c["case_id"]),
                                int(c["attempt"]),
                                candidate,
                            )
                        )
                        in metric_map
                    ]
                    break

        observed = _aggregate_case_metrics(
            dataset_cases,
            deployment=str(sample_cell.get("deployment") or ""),
        )
        dataset_pricing = _pricing_for_model(
            run_pricing,
            run_id=str(sample_cell["run_id"]),
            model_key=model_key,
            model_id=sample_cell.get("model_id"),
            effective_model_id=sample_cell.get("effective_model_id"),
            provider_key=sample_cell.get("provider_key"),
        )
        dataset_summaries.append(
            {
                "model_key": model_key,
                "model_signature": sample_cell["model_signature"],
                "capability_id": capability_id,
                "dataset_id": dataset_id,
                "primary_metric": resolved_metric,
                "primary_value": _mean(values),
                "normalized_quality_score": (
                    _mean(values) * 100.0 if values else None
                ),
                "sample_count": len(dataset_cases),
                **observed,
                "provider_cost_pricing": dataset_pricing,
            }
        )

    dataset_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in dataset_summaries:
        dataset_groups[
            (str(row["capability_id"]), str(row["dataset_id"]))
        ].append(row)
    for rows in dataset_groups.values():
        _annotate_pareto(rows, y_key="normalized_quality_score")

    return {
        "schema_version": "2",
        "quality_policy": QUALITY_POLICY,
        "cohort_policy": {
            "policy_id": "max-model-coverage-latest-v1",
            "description": (
                "Per capability, use the CURRENT benchmark lineage with the "
                "largest model coverage; break ties by latest completion."
            ),
            "benchmark_signatures": selected_signatures,
        },
        "model_summaries": model_summaries,
        "capability_summaries": capability_summaries,
        "dataset_summaries": dataset_summaries,
    }
