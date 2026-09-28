"""Data extraction, filtering, and metric calculation for benchmark reporting."""

from __future__ import annotations

import json
import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from jev_bench.reporting.config import get_series_name, load_reporting_config


@lru_cache(maxsize=1)
def load_benchmark_registry() -> dict[str, Any]:
    """Load model registry definitions from benchmark-models.yaml."""
    candidates = [
        Path("benchmark-models.yaml"),
        Path(__file__).resolve().parents[3] / "benchmark-models.yaml",
    ]
    for c in candidates:
        if c.is_file():
            try:
                with c.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    return data.get("models", {})
            except Exception:
                pass
    return {}


@lru_cache(maxsize=1)
def load_experiments_config() -> dict[str, Any]:
    """Load settings from experiments_config.yaml."""
    candidates = [
        Path("experiments_config.yaml"),
        Path(__file__).resolve().parents[3] / "experiments_config.yaml",
    ]
    for c in candidates:
        if c.is_file():
            try:
                with c.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
    return {}


@lru_cache(maxsize=256)
def _get_manifest_parameters(run_group: str) -> dict[str, Any]:
    """Retrieve parameters dictionary from manifest JSON for a run_group."""
    candidates = [
        Path("results/manifests") / f"{run_group}.json",
        Path(__file__).resolve().parents[3] / "results/manifests" / f"{run_group}.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                with c.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("parameters", {})
            except Exception:
                pass
    return {}


def resolve_dataset_type(row: Any) -> str:
    """Classify the dataset as 'public' (Banking77/CLINC150, 77 cases) or 'smoke' (24 cases)."""
    if "dataset_type" in row and pd.notna(row["dataset_type"]) and str(row["dataset_type"]).strip():
        return str(row["dataset_type"]).strip().lower()
    exp = str(row.get("experiment", "") or "").strip().lower()
    suite = str(row.get("suite", "") or "").strip().lower()
    ds = str(row.get("dataset", "") or "").strip().lower()
    if "smoke" in suite or ds == "smoke":
        return "smoke"
    if exp.endswith("-public") or "public" in suite or ds not in {"", "nan", "none"}:
        return "public"
    return "smoke"


def resolve_thinking_mode(row: Any) -> str:
    """Identify if thinking/reasoning was on ('on'), off ('off'), or standard/cloud ('standard')."""
    prov = str(row.get("provider", "") or "").strip().lower()
    if prov not in {"local-korgis", "korgis"}:
        return "standard"

    if "thinking_mode" in row and pd.notna(row["thinking_mode"]) and str(row["thinking_mode"]).strip():
        return str(row["thinking_mode"]).strip().lower()

    if "enable_thinking" in row and pd.notna(row["enable_thinking"]):
        return "on" if bool(row["enable_thinking"]) else "off"

    rg = str(row.get("run_group", "") or "").strip()
    if rg:
        # Known thinking runs in history
        if rg in {"69c47e20-5640-4410-8779-333160a09a22", "0d77c495-c8e8-4aa9-a5f8-0e2dfd93f01c"}:
            return "on"
        params = _get_manifest_parameters(rg)
        if "enable_thinking" in params:
            return "on" if params["enable_thinking"] else "off"

    # Token heuristic: if average output tokens > 150 on classification, thinking was on
    out_tokens = row.get("output_tokens")
    if pd.notna(out_tokens) and float(out_tokens) > 150:
        return "on"

    return "off"


def resolve_dataset_name(row: Any) -> str:
    value = row.get("dataset")
    if pd.notna(value) and str(value).strip() and str(value) != "public":
        return str(value).strip().lower()
    return "banking77" if canonical_task_name(row.get("experiment", "")) == "routing" else "public"


def resolve_configuration(row: Any) -> str:
    """Use recorded configuration only, never today's model registry defaults."""
    explicit = row.get("configuration_id")
    if pd.notna(explicit) and str(explicit).strip():
        return str(explicit)
    params = _get_manifest_parameters(str(row.get("run_group", "")))
    values = {}
    fields = ["temperature", "top_p", "top_k", "max_tokens", "max_output_tokens",
              "ctx_size", "sampling", "response_format", "output_contract"]
    if row.get("provider") == "llm-workflow":
        fields.append("openai_reasoning_effort")
    for key in fields:
        value = row.get(key, params.get(key))
        if isinstance(value, (dict, list)) or (pd.notna(value) and str(value).strip()):
            values[key] = value
    # An absent cloud effort and the documented default describe the same config.
    if values.get("openai_reasoning_effort") == "none":
        values.pop("openai_reasoning_effort")
    if not values:
        return ""
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()[:8]


def with_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Add series display name and metadata columns to DataFrame."""
    if frame.empty:
        frame = frame.copy()
        frame["series"] = []
        frame["dataset_type"] = []
        frame["thinking_mode"] = []
        return frame
    frame = frame.copy()

    # Ensure dataset_type and thinking_mode are fully resolved for EVERY row (never NaN or missing)
    resolved_ds = [
        str(r["dataset_type"]).strip().lower()
        if ("dataset_type" in r and pd.notna(r["dataset_type"]) and str(r["dataset_type"]).strip())
        else resolve_dataset_type(r)
        for _, r in frame.iterrows()
    ]
    resolved_th = [
        str(r["thinking_mode"]).strip().lower()
        if ("thinking_mode" in r and pd.notna(r["thinking_mode"]) and str(r["thinking_mode"]).strip())
        else resolve_thinking_mode(r)
        for _, r in frame.iterrows()
    ]
    frame["dataset_type"] = resolved_ds
    frame["thinking_mode"] = resolved_th
    configs = [resolve_configuration(r) for _, r in frame.iterrows()]

    series_names = []
    for idx, r in frame.iterrows():
        base = get_series_name(str(r.get("provider", "")), str(r.get("model", "")))
        th = resolved_th[len(series_names)]
        ds = resolved_ds[len(series_names)]
        if th == "on" and ds == "smoke":
            series_names.append(f"{base} (Thinking · Smoke)")
        elif th == "on":
            series_names.append(f"{base} (Thinking)")
        elif ds == "smoke":
            series_names.append(f"{base} (Smoke)")
        else:
            series_names.append(base)
    frame["series"] = [f"{name} · {config}" if config else name
                       for name, config in zip(series_names, configs)]
    return frame


def canonical_task_name(experiment: str) -> str:
    """Normalize experiment tags like '01-routing-public' or '01-routing' to 'routing'."""
    clean = str(experiment).strip().lower()
    for prefix in ["01-", "02-", "03-", "04-", "05-"]:
        clean = clean.removeprefix(prefix)
    clean = clean.replace("-public", "").replace("_", "-")
    return clean


def select_run_group(
    rows: pd.DataFrame, run_group: str | None = None
) -> tuple[pd.DataFrame, str | None]:
    """Select the appropriate run group from raw results.

    When 'latest_per_model' is requested:
    Picks the latest run group for each (model, dataset_type, thinking_mode, canonical_task) combination.
    This guarantees that:
      - Runs on different datasets (Banking77 vs Smoke) do not hide or displace each other.
      - Runs with different configurations (thinking: on vs thinking: off) are both preserved.
      - Each model-configuration-dataset combination consistently presents its most recent results.
    """
    if "run_group" not in rows.columns or rows.empty:
        return rows, None

    if run_group and run_group not in {"latest_per_model", "all_latest", "all"}:
        selected = rows[rows["run_group"] == run_group].copy()
        if selected.empty:
            raise ValueError(f"run_group not found: {run_group}")
        return selected, run_group

    if "model" in rows.columns and "experiment" in rows.columns:
        df_copy = rows.copy()
        if "run_timestamp_utc" not in df_copy:
            df_copy["run_timestamp_utc"] = None
        df_copy["_task"] = df_copy["experiment"].apply(canonical_task_name)
        df_copy["_dataset_type"] = [
            str(r["dataset_type"]).strip().lower()
            if ("dataset_type" in r and pd.notna(r["dataset_type"]) and str(r["dataset_type"]).strip())
            else resolve_dataset_type(r)
            for _, r in df_copy.iterrows()
        ]
        df_copy["_thinking_mode"] = [
            str(r["thinking_mode"]).strip().lower()
            if ("thinking_mode" in r and pd.notna(r["thinking_mode"]) and str(r["thinking_mode"]).strip())
            else resolve_thinking_mode(r)
            for _, r in df_copy.iterrows()
        ]

        df_copy["_dataset"] = df_copy.apply(resolve_dataset_name, axis=1)
        df_copy["_configuration"] = df_copy.apply(resolve_configuration, axis=1)
        df_copy["_timestamp"] = pd.to_datetime(df_copy["run_timestamp_utc"], utc=True, errors="coerce")
        df_sorted = df_copy.sort_values("_timestamp", na_position="first", kind="stable")
        keys = ["provider", "model", "_dataset_type", "_dataset", "_thinking_mode", "_configuration", "_task"]
        run_key = "run_id" if "run_id" in rows and rows["run_id"].notna().all() else "run_group"

        # Select latest run_group per (model, dataset_type, thinking_mode, task)
        latest_pairs = (
            df_sorted.groupby(keys, dropna=False)[run_key]
            .last()
            .reset_index()
        )
        selected = pd.merge(
            df_copy,
            latest_pairs,
            on=[*keys, run_key],
            how="inner",
        ).drop(columns=["_task", "_dataset_type", "_thinking_mode", "_dataset", "_configuration", "_timestamp"])
        return selected, "latest_per_model"

    if "run_timestamp_utc" in rows.columns:
        latest = rows.sort_values("run_timestamp_utc").iloc[-1]["run_group"]
    else:
        latest = rows.iloc[-1]["run_group"]
    return rows[rows["run_group"] == latest].copy(), str(latest)


def compute_overview(rows: pd.DataFrame) -> pd.DataFrame:
    """Compute top-level summary metrics per model, configuration, and dataset across requests."""
    if rows.empty:
        return pd.DataFrame()

    with_s = with_series(rows)
    records = []

    group_cols = ["provider", "model", "series", "dataset_type", "thinking_mode"]
    for col in ["dataset_type", "thinking_mode"]:
        if col not in with_s.columns or with_s[col].isna().any():
            if col == "dataset_type":
                with_s["dataset_type"] = [
                    resolve_dataset_type(r)
                    if (col not in r or pd.isna(r[col]) or not str(r[col]).strip())
                    else str(r[col]).strip().lower()
                    for _, r in with_s.iterrows()
                ]
            elif col == "thinking_mode":
                with_s["thinking_mode"] = [
                    resolve_thinking_mode(r)
                    if (col not in r or pd.isna(r[col]) or not str(r[col]).strip())
                    else str(r[col]).strip().lower()
                    for _, r in with_s.iterrows()
                ]

    for (provider, model, series, dataset_type, thinking_mode), group in with_s.groupby(group_cols, dropna=False):
        reqs = group.sort_values("case_id").drop_duplicates(
            ["experiment", "case_id", "provider", "model"]
        )
        valid_reqs = reqs[reqs["valid"] == True]

        # Effective accuracy: evaluated on ALL primary metric requests (invalid choices count as incorrect)
        primary_all = group[group["primary_metric"].fillna(False) == True]
        effective_acc = (
            float(primary_all["correct"].fillna(False).mean())
            if len(primary_all) > 0
            else math.nan
        )

        # Conditioned accuracy: evaluated strictly on valid requests
        valid = group[group["valid"] == True]  # noqa: E712
        primary_valid = valid[valid["primary_metric"].fillna(False) == True]  # noqa: E712
        valid_acc = (
            float(primary_valid["correct"].mean())
            if len(primary_valid) > 0
            else math.nan
        )

        costs = (
            valid_reqs["estimated_cost_usd"].dropna()
            if "estimated_cost_usd" in valid_reqs
            else pd.Series(dtype=float)
        )
        latencies = valid_reqs["latency_ms"].dropna()

        total_count = len(reqs)
        valid_count = len(valid_reqs)
        valid_rate = (valid_count / total_count) if total_count > 0 else 0.0

        datasets = sorted({resolve_dataset_name(r) for _, r in group.iterrows()})
        ds_label = " + ".join(datasets)
        series_id = f"{provider}__{series}__{dataset_type}__{thinking_mode}"

        records.append(
            {
                "provider": provider,
                "model": model,
                "series": series,
                "series_id": series_id,
                "dataset": dataset_type,
                "dataset_label": ds_label,
                "thinking_mode": thinking_mode,
                "accuracy": effective_acc,
                "valid_accuracy": valid_acc,
                "valid_rate": valid_rate,
                "latency_p50_ms": float(latencies.median()) if len(latencies) > 0 else math.nan,
                "latency_p95_ms": float(latencies.quantile(0.95)) if len(latencies) > 0 else math.nan,
                "cost_per_request_usd": float(costs.mean()) if len(costs) > 0 else math.nan,
                "cost_per_1k_requests_usd": float(costs.mean() * 1000) if len(costs) > 0 else 0.0,
                "run_cost_usd": float(costs.sum()) if len(costs) > 0 else 0.0,
                "requests": total_count,
                "valid_requests": valid_count,
                "latest_run_at": str(group["run_timestamp_utc"].max()) if "run_timestamp_utc" in group else None,
                "run_ids": sorted(group["run_id"].dropna().unique().tolist()) if "run_id" in group else [],
            }
        )

    df = pd.DataFrame(records)
    if not df.empty and "accuracy" in df.columns:
        df = df.sort_values(by=["accuracy", "latency_p50_ms"], ascending=[False, True])
    return df


def compute_leaderboard(overview: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute ranked leaderboard with comparative gaps, datasets, and performance badges."""
    if overview.empty or "accuracy" not in overview.columns:
        return []

    valid_models = overview[overview["accuracy"].notna()].copy()
    if valid_models.empty:
        return []

    sorted_df = valid_models.sort_values(
        by=["accuracy", "latency_p50_ms"], ascending=[False, True]
    ).reset_index(drop=True)

    leader_acc = float(sorted_df.iloc[0]["accuracy"])
    fastest_lat = float(sorted_df["latency_p50_ms"].min())
    slowest_lat = float(sorted_df["latency_p50_ms"].max())

    leaderboard: list[dict[str, Any]] = []
    registry = load_benchmark_registry()

    # Find sweet spot: highest accuracy among models with latency <= 3500ms (or fastest 50%)
    sweet_spot_model = None
    sub_3s = sorted_df[sorted_df["latency_p50_ms"] <= 3500.0]
    if not sub_3s.empty:
        candidate = sub_3s.iloc[0]
        # Only tag as sweet spot if it's not already the overall accuracy leader
        if candidate["series"] != sorted_df.iloc[0]["series"] and candidate["accuracy"] >= 0.40:
            sweet_spot_model = candidate["series"]

    for idx, row in sorted_df.iterrows():
        rank = idx + 1
        acc = float(row["accuracy"])
        lat = float(row["latency_p50_ms"]) if pd.notna(row["latency_p50_ms"]) else math.nan

        # Gap vs Leader
        gap_pts = acc - leader_acc  # negative or 0
        if rank == 1:
            delta_str = "Leader"
            delta_class = "leader"
        else:
            pct_diff = gap_pts * 100
            delta_str = f"{pct_diff:+.1f}%"
            if abs(pct_diff) < 8.0:
                delta_class = "close"
            elif abs(pct_diff) < 20.0:
                delta_class = "moderate"
            else:
                delta_class = "far"

        # Speedup vs slowest or leader
        if pd.notna(lat) and lat > 0:
            if lat == fastest_lat:
                speed_str = "Fastest"
                speed_class = "fastest"
            elif lat == slowest_lat:
                speed_str = "Baseline"
                speed_class = "baseline"
            else:
                multiplier = slowest_lat / lat
                speed_str = f"{multiplier:.1f}x faster"
                speed_class = "faster"
        else:
            speed_str = "—"
            speed_class = "neutral"

        # Speedup vs accuracy leader
        leader_lat = float(sorted_df.iloc[0]["latency_p50_ms"])
        if pd.notna(lat) and lat > 0 and pd.notna(leader_lat) and leader_lat > 0:
            if rank == 1:
                vs_leader_speed = "1.0x"
            else:
                ratio = leader_lat / lat
                if ratio >= 1.1:
                    vs_leader_speed = f"{ratio:.1f}x faster"
                elif ratio <= 0.9:
                    vs_leader_speed = f"{(lat / leader_lat):.1f}x slower"
                else:
                    vs_leader_speed = "~same speed"
        else:
            vs_leader_speed = "—"

        # Badge assignment
        badges = []
        if rank == 1:
            badges.append({"label": "🏆 Top Accuracy", "class": "badge-gold"})
        if pd.notna(lat) and lat == fastest_lat:
            badges.append({"label": "⚡ Fastest", "class": "badge-blue"})
        if row["series"] == sweet_spot_model:
            badges.append({"label": "⚖️ Sweet Spot", "class": "badge-emerald"})

        # Thinking badge
        row_thinking = str(row.get("thinking_mode", "off")).lower()
        if row_thinking == "on":
            badges.append({"label": "🧠 Think: ON", "class": "badge-purple"})

        # Dataset badge
        row_dataset = str(row.get("dataset", "public")).lower()
        badges.append({"label": str(row.get("dataset_label", row_dataset)), "class": "badge-indigo"})

        # Quantization / Architecture badge
        q_label = ""
        series_lower = str(row["series"]).lower()
        if "q8_0" in series_lower or "q8" in series_lower:
            q_label = "Q8"
        elif "q4_k_m" in series_lower or "q4km" in series_lower:
            q_label = "Q4_K_M"

        # Medal icon
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

        # Execution parameters for local models
        exec_params = None
        if str(row["provider"]) == "local-korgis":
            m_key = str(row["model"])
            reg_entry = registry.get(m_key, {})
            p_dict = reg_entry.get("params", {})
            exp_cfg = load_experiments_config()
            is_thinking_on = (row_thinking == "on")
            max_out = (
                int(exp_cfg.get("thinking_max_output_tokens", 2048))
                if is_thinking_on
                else int(exp_cfg.get("max_output_tokens", 512))
            )
            exec_params = {
                "ctx_size": p_dict.get("ctx_size", 8192),
                "max_output_tokens": max_out,
                "temperature": p_dict.get("default_temperature", 0.0),
                "thinking_mode": row_thinking,
                "backend": reg_entry.get("backend", "llama_server"),
                "quantization": reg_entry.get("quantization", q_label or "GGUF"),
            }

        leaderboard.append(
            {
                "rank": rank,
                "medal": medal,
                "series": str(row["series"]),
                "series_id": str(row.get("series_id", row["series"])),
                "model": str(row["model"]),
                "provider": str(row["provider"]),
                "dataset": row_dataset,
                "latest_run_at": row.get("latest_run_at"),
                "run_ids": row.get("run_ids", []),
                "dataset_label": str(row.get("dataset_label", "Banking77 (77)" if row_dataset == "public" else "Smoke (24)")),
                "thinking_mode": row_thinking,
                "accuracy": acc,
                "accuracy_pct": f"{acc * 100:.1f}%",
                "valid_accuracy": float(row.get("valid_accuracy", acc)) if pd.notna(row.get("valid_accuracy")) else acc,
                "valid_accuracy_pct": f"{float(row.get('valid_accuracy', acc)) * 100:.1f}%" if pd.notna(row.get("valid_accuracy")) else f"{acc * 100:.1f}%",
                "delta_str": delta_str,
                "delta_class": delta_class,
                "latency_p50_ms": lat,
                "latency_str": f"{lat:.0f} ms" if pd.notna(lat) else "—",
                "speed_str": speed_str,
                "speed_class": speed_class,
                "vs_leader_speed": vs_leader_speed,
                "valid_rate_pct": f"{float(row['valid_rate']) * 100:.1f}%",
                "valid_count": int(row["valid_requests"]),
                "total_count": int(row["requests"]),
                "badges": badges,
                "quant_label": q_label,
                "execution_params": exec_params,
            }
        )

    return leaderboard


def compute_kpi_cards(leaderboard: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract executive summary cards from leaderboard."""
    if not leaderboard:
        return {"total_models": 0, "total_requests": 0}

    leader = leaderboard[0]
    fastest = min(leaderboard, key=lambda x: x["latency_p50_ms"] if pd.notna(x["latency_p50_ms"]) else 999999)

    # Sweet spot: model tagged or 2nd place
    sweet_spot = next((m for m in leaderboard if any(b["label"] == "⚖️ Sweet Spot" for b in m["badges"])), None)
    if not sweet_spot and len(leaderboard) > 1:
        sweet_spot = leaderboard[1]

    total_requests = sum(m["total_count"] for m in leaderboard)

    return {
        "leader": leader,
        "fastest": fastest,
        "sweet_spot": sweet_spot,
        "total_models": len(leaderboard),
        "total_requests": total_requests,
    }


def get_active_experiments(rows: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Determine case count and active status for each standard experiment."""
    cfg = load_reporting_config().get("experiments", {})
    status: dict[str, dict[str, Any]] = {}

    for exp_id, meta in cfg.items():
        tag = meta.get("tag", "")
        pub_tag = meta.get("public_tag", "")

        matches = rows[rows["experiment"].isin([tag, pub_tag])] if not rows.empty else pd.DataFrame()
        count = len(matches)
        models_count = matches["model"].nunique() if count > 0 else 0

        status[exp_id] = {
            "id": exp_id,
            "title": meta.get("title", exp_id.title()),
            "full_title": meta.get("full_title", exp_id.title()),
            "description": meta.get("description", ""),
            "cli_command": meta.get("cli_command", ""),
            "has_data": count > 0,
            "count": count,
            "models_count": models_count,
            "badge_text": f"{count} cases" if count > 0 else "Not evaluated",
            "badge_class": "badge-has-data" if count > 0 else "badge-empty",
        }

    return status
