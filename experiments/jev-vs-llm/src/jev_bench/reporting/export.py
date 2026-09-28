"""Export benchmark results to structured JSON payload for React UI."""

from __future__ import annotations

import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from jev_bench.costs import pricing_metadata
from jev_bench.metrics import (
    calibration_summary,
    coverage_curve,
    difficulty_summary,
    reliability_bins,
    summarize,
    top_confusions,
)
from jev_bench.reporting.data import (
    compute_kpi_cards,
    compute_leaderboard,
    compute_overview,
    get_active_experiments,
    select_run_group,
    resolve_dataset_type,
    resolve_dataset_name,
    with_series,
)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or pd.isna(val) or math.isnan(float(val)):
        return default
    return float(val)


def _clean_df(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert dataframe to JSON-safe list of dicts, replacing NaNs."""
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                r[k] = None
            elif isinstance(v, (pd.Timestamp,)):
                r[k] = str(v)
    return records


def _extract_cases(rows: pd.DataFrame, prefix: str, max_cases: int = 250) -> list[dict[str, Any]]:
    """Extract case cards for the case explorer."""
    public_name = f"{prefix}-public"
    subset = rows[rows["experiment"].isin([public_name, prefix])].copy()
    if subset.empty:
        return []

    subset = with_series(subset)
    cases = []

    # Sort and take recent cases
    for (series, case_id), frame in subset.groupby(["series", "case_id"], sort=False):
        first = frame.iloc[0]
        valid = bool(frame["valid"].all())
        primary = frame[frame["primary_metric"].fillna(False) == True]

        if not valid:
            status = "Invalid"
            status_class = "bad"
        elif len(primary) and bool(primary["correct"].all()):
            status = "Correct"
            status_class = "good"
        elif len(primary):
            status = "Wrong"
            status_class = "bad"
        else:
            status = "Valid"
            status_class = "neutral"

        exp_val = primary.iloc[-1].get("expected") if len(primary) else first.get("expected")
        act_val = primary.iloc[-1].get("actual") if len(primary) else first.get("actual")

        decisions = []
        for _, row in frame.iterrows():
            decisions.append({
                "question_id": str(row.get("question_id") or ""),
                "expected": str(row.get("expected") or ""),
                "actual": str(row.get("actual") or ""),
                "correct": bool(row.get("correct")),
                "valid": bool(row.get("valid")),
                "confidence": _safe_float(row.get("confidence"), 0.0),
                "error": str(row.get("error") or "") if pd.notna(row.get("error")) else None,
            })

        cases.append({
            "series": str(series),
            "model": str(first.get("model") or ""),
            "case_id": str(case_id),
            "status": status,
            "status_class": status_class,
            "latency_ms": _safe_float(first.get("latency_ms"), 0.0),
            "input_state": str(first.get("input_state") or ""),
            "expected": str(exp_val or ""),
            "actual": str(act_val or ""),
            "correct": bool(status == "Correct"),
            "valid": valid,
            "error": str(first.get("error") or "") if pd.notna(first.get("error")) else None,
            "difficulty": str(first.get("difficulty") or "in_scope"),
            "decisions": decisions,
        })
        if len(cases) >= max_cases:
            break

    return cases


def _extract_errors(rows: pd.DataFrame, prefix: str) -> list[dict[str, Any]]:
    """Extract schema/provider failures."""
    subset = rows[rows["experiment"].isin([f"{prefix}-public", prefix])].copy()
    if subset.empty:
        return []
    subset = with_series(subset)
    errors = subset[(subset["valid"] == False) | subset["error"].notna()].copy()
    if errors.empty:
        return []
    cols = ["series", "case_id", "question_id", "error", "latency_ms", "input_tokens", "output_tokens"]
    available = [c for c in cols if c in errors.columns]
    return _clean_df(errors[available].drop_duplicates())


def _extract_per_class(rows: pd.DataFrame, prefix: str) -> list[dict[str, Any]]:
    """Extract per-class accuracy breakdown."""
    subset = rows[
        rows["experiment"].isin([f"{prefix}-public", prefix])
        & rows["primary_metric"].fillna(False)
        & rows["expected"].notna()
    ].copy()
    if subset.empty:
        return []
    subset = with_series(subset)
    records = []
    for (series, expected), frame in subset.groupby(["series", "expected"], dropna=False):
        valid = frame[frame["valid"] == True]
        wrong = valid[(valid["correct"] == False) & valid["actual"].notna()]
        top_wrong = wrong["actual"].astype(str).value_counts().index[0] if not wrong.empty else "—"
        records.append({
            "series": str(series),
            "class": str(expected),
            "cases": int(frame["case_id"].nunique()),
            "valid_rate": float(frame.groupby("case_id")["valid"].all().mean()),
            "accuracy": float(valid["correct"].mean()) if len(valid) else 0.0,
            "top_wrong": str(top_wrong),
        })
    return sorted(records, key=lambda x: (x["series"], -x["accuracy"]))


def _detect_hardware() -> dict[str, str | None]:
    """Auto-detect the host hardware specs for local benchmark context.

    On macOS, uses ``system_profiler SPHardwareDataType`` to extract chip name,
    core count, and unified memory size.  Returns a dict safe for JSON
    serialisation; unknown fields are ``None``.
    """
    result: dict[str, str | None] = {
        "device": None,
        "chip": None,
        "cores": None,
        "memory_gb": None,
        "os": platform.system(),
    }

    # Allow explicit override via environment variables
    env_device = os.getenv("BENCHMARK_HARDWARE_DEVICE")
    env_chip = os.getenv("BENCHMARK_HARDWARE_CHIP")
    env_memory = os.getenv("BENCHMARK_HARDWARE_MEMORY_GB")
    if env_device or env_chip:
        result["device"] = env_device
        result["chip"] = env_chip
        result["memory_gb"] = env_memory
        return result

    if platform.system() != "Darwin":
        return result

    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"],
            timeout=10,
            text=True,
        )
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("Model Name:"):
                result["device"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Chip:"):
                result["chip"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Total Number of Cores:"):
                result["cores"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Memory:"):
                mem_str = stripped.split(":", 1)[1].strip()
                result["memory_gb"] = mem_str.replace(" GB", "")
    except Exception:
        pass  # graceful fallback: fields stay None

    return result


def _load_local_parameters() -> dict[str, Any]:
    """Extract configured execution parameters for local models."""
    root = Path(__file__).resolve().parents[3]
    exp_cfg_path = root / "experiments_config.yaml"
    reg_path = root / "benchmark-models.yaml"

    enable_thinking = False
    max_output_tokens = 512
    if exp_cfg_path.is_file():
        try:
            with exp_cfg_path.open("r", encoding="utf-8") as f:
                c = yaml.safe_load(f) or {}
                enable_thinking = bool(c.get("enable_thinking", False))
                max_output_tokens = int(c.get("max_output_tokens", 512))
                if enable_thinking and max_output_tokens <= 512:
                    max_output_tokens = int(c.get("thinking_max_output_tokens", 2048))
        except Exception:
            pass

    ctx_size = 8192
    if reg_path.is_file():
        try:
            with reg_path.open("r", encoding="utf-8") as f:
                m = yaml.safe_load(f) or {}
                for model_data in m.get("models", {}).values():
                    params = model_data.get("params", {})
                    if "ctx_size" in params:
                        ctx_size = int(params["ctx_size"])
                        break
        except Exception:
            pass

    return {
        "context_window_tokens": ctx_size,
        "max_output_tokens": max_output_tokens,
        "temperature": 0.0,
        "thinking_policy": "enabled (on)" if enable_thinking else "disabled (off)",
        "inference_runtime": "llama-server (Homebrew llama.cpp)",
        "hardware_acceleration": "Apple Silicon Metal (Unified Memory)",
        "batch_slots": "1 parallel slot · continuous batching · unified KV",
    }


def build_benchmark_payload(
    raw_csv: Path, run_group: str | None = "latest_per_model"
) -> dict[str, Any]:
    """Generate complete structured dictionary for the React dashboard."""
    all_rows = pd.read_csv(raw_csv)
    # Dashboard policy is always latest per configuration, including failed runs.
    public_rows = all_rows[all_rows.apply(resolve_dataset_type, axis=1).ne("smoke")].copy()
    rows, selected_group = select_run_group(public_rows, "latest_per_model")
    hardware = _detect_hardware()
    payload = _build_view(rows, selected_group, hardware)
    datasets = []
    views = {}
    dataset_names = rows.apply(resolve_dataset_name, axis=1) if not rows.empty else pd.Series(dtype=str)
    for name in sorted(dataset_names.unique()):
        view = _build_view(rows[dataset_names.eq(name)].copy(), selected_group, hardware)
        label = {"banking77": "BANKING77", "clinc150": "CLINC150"}.get(name, name)
        datasets.append({"id": name, "label": label, "count": len(view["models"])})
        views[name] = view
    payload["datasets"] = datasets
    payload["dataset_views"] = views
    return payload


def _series_metrics(rows: pd.DataFrame, metric, **kwargs) -> pd.DataFrame:
    """Keep model configurations separate in every drill-down metric."""
    outputs = []
    for series, group in with_series(rows).groupby("series", sort=False):
        result = metric(group, **kwargs).copy()
        result["series"] = series
        outputs.append(result)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def _build_view(rows: pd.DataFrame, selected_group: str | None, hardware: dict) -> dict[str, Any]:
    overview_df = compute_overview(rows)
    leaderboard = compute_leaderboard(overview_df)
    kpis = compute_kpi_cards(leaderboard)
    active_exps = get_active_experiments(rows)
    pricing = pricing_metadata()

    # Determine if run is 100% local (all estimated API costs are 0)
    total_api_cost = float(rows["estimated_cost_usd"].dropna().sum()) if "estimated_cost_usd" in rows.columns else 0.0
    is_local_zero_cost = (total_api_cost == 0.0)

    # Suite and runner info
    suite = ", ".join(sorted(rows["suite"].dropna().astype(str).unique())) if "suite" in rows.columns else "unspecified"
    runner = ", ".join(sorted(rows["runner_location"].dropna().astype(str).unique())) if "runner_location" in rows.columns else "unspecified"

    # Models list with series names and colors
    models_list = []
    for m in leaderboard:
        models_list.append({
            "series": m["series"],
            "series_id": m.get("series_id", m["series"]),
            "model": m["model"],
            "provider": m["provider"],
            "dataset": m.get("dataset", "public"),
            "dataset_label": m.get("dataset_label", ""),
            "thinking_mode": m.get("thinking_mode", "off"),
            "accuracy": m["accuracy"],
            "latency_p50_ms": m["latency_p50_ms"],
        })

    # Summary table per experiment
    summary_df = _series_metrics(rows, summarize)
    if "experiment" not in summary_df:
        summary_df["experiment"] = pd.Series(dtype=str)

    # Routing section
    routing_summary = _clean_df(
        summary_df[summary_df["experiment"].isin(["01-routing-public", "01-routing"])]
    )
    confusions_df = _series_metrics(rows, top_confusions, limit=12)
    confusions = _clean_df(confusions_df)
    routing_per_class = _extract_per_class(rows, "01-routing")
    routing_cases = _extract_cases(rows, "01-routing")
    routing_errors = _extract_errors(rows, "01-routing")

    # Calibration section
    cal_summary = _clean_df(_series_metrics(rows, calibration_summary))
    rel_bins = _clean_df(_series_metrics(rows, reliability_bins))
    coverage = _clean_df(_series_metrics(rows, coverage_curve))
    difficulty = _clean_df(_series_metrics(rows, difficulty_summary))
    cal_cases = _extract_cases(rows, "02-calibration")
    cal_errors = _extract_errors(rows, "02-calibration")

    # Scaling section
    scaling_rows = rows[rows["experiment"].eq("03-parallel-scaling") & (rows["valid"] == True)].copy()
    scaling_summary = []
    scaling_detail = []
    if not scaling_rows.empty:
        sc_with_s = with_series(scaling_rows)
        grouped = (
            sc_with_s.groupby(["series", "question_count"], as_index=False)
            .agg(
                latency_p50_ms=("latency_ms", "median"),
                latency_p95_ms=("latency_ms", lambda x: float(x.quantile(0.95))),
                cost_per_request_usd=("estimated_cost_usd", "mean"),
            )
        )
        scaling_summary = _clean_df(grouped)
        scaling_detail = _clean_df(sc_with_s[[
            c for c in ["series", "case_id", "question_count", "valid", "latency_ms", "estimated_cost_usd", "error"]
            if c in sc_with_s.columns
        ]])
    scaling_errors = _extract_errors(rows, "03-parallel-scaling")

    # Workflow section
    workflow_summary = _clean_df(summary_df[summary_df["experiment"].eq("04-workflow")])
    workflow_cases = _extract_cases(rows, "04-workflow")
    workflow_errors = _extract_errors(rows, "04-workflow")

    # Agent section
    agent_summary = _clean_df(summary_df[summary_df["experiment"].eq("05-hybrid-agent")])
    agent_cases = _extract_cases(rows, "05-hybrid-agent")
    agent_errors = _extract_errors(rows, "05-hybrid-agent")

    return {
        "metadata": {
            "run_group": selected_group or "latest",
            "suite": suite,
            "runner_location": runner,
            "pricing_as_of": pricing.get("as_of", "latest"),
            "total_rows": len(rows),
            "is_local_zero_cost": is_local_zero_cost,
            "hardware": hardware,
            "local_parameters": _load_local_parameters(),
        },
        "experiments": active_exps,
        "models": models_list,
        "leaderboard": leaderboard,
        "kpi_cards": kpis,
        "overview": _clean_df(overview_df),
        "routing": {
            "summary": routing_summary,
            "confusions": confusions,
            "per_class": routing_per_class,
            "cases": routing_cases,
            "errors": routing_errors,
        },
        "calibration": {
            "summary": cal_summary,
            "rel_bins": rel_bins,
            "coverage": coverage,
            "difficulty": difficulty,
            "cases": cal_cases,
            "errors": cal_errors,
        },
        "scaling": {
            "summary": scaling_summary,
            "details": scaling_detail,
            "errors": scaling_errors,
        },
        "workflow": {
            "summary": workflow_summary,
            "cases": workflow_cases,
            "errors": workflow_errors,
        },
        "agent": {
            "summary": agent_summary,
            "cases": agent_cases,
            "errors": agent_errors,
        },
        "pricing": pricing,
    }


def export_benchmark_json(raw_csv: Path, output_json: Path, run_group: str | None = "latest_per_model") -> dict[str, Any]:
    """Export benchmark payload to a JSON file."""
    data = build_benchmark_payload(raw_csv, run_group)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data
