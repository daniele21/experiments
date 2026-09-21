"""Data extraction, filtering, and metric calculation for benchmark reporting."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from jev_bench.reporting.config import get_series_name, load_reporting_config


def with_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Add series display name column to DataFrame."""
    if frame.empty:
        frame = frame.copy()
        frame["series"] = []
        return frame
    frame = frame.copy()
    frame["series"] = [
        get_series_name(str(provider), str(model))
        for provider, model in zip(frame["provider"], frame["model"], strict=False)
    ]
    return frame


def canonical_task_name(experiment: str) -> str:
    """Normalize experiment tags like '01-routing-public' or '01-routing' to 'routing'."""
    clean = str(experiment).strip().lower()
    for prefix in ["01-", "02-", "03-", "04-", "05-"]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    clean = clean.replace("-public", "").replace("_", "-")
    return clean


def select_run_group(
    rows: pd.DataFrame, run_group: str | None = None
) -> tuple[pd.DataFrame, str | None]:
    """Select the appropriate run group from raw results.

    When 'latest_per_model' is requested:
    Picks the latest run group for each (model, canonical_task) pair.
    If both a public dataset run and smoke run exist, prefers the latest run
    (or public run) to prevent dilution and preserve apples-to-apples comparison.
    """
    if "run_group" not in rows.columns or rows.empty:
        return rows, None

    if run_group and run_group not in {"latest_per_model", "all_latest", "all"}:
        selected = rows[rows["run_group"] == run_group].copy()
        if selected.empty:
            raise ValueError(f"run_group not found: {run_group}")
        return selected, run_group

    if "run_timestamp_utc" in rows.columns and "model" in rows.columns and "experiment" in rows.columns:
        df_copy = rows.copy()
        df_copy["_task"] = df_copy["experiment"].apply(canonical_task_name)
        df_sorted = df_copy.sort_values("run_timestamp_utc")

        # Select latest run_group per (model, task)
        latest_pairs = (
            df_sorted.groupby(["model", "_task"])["run_group"]
            .last()
            .reset_index()
        )
        selected = pd.merge(
            df_copy,
            latest_pairs,
            on=["model", "_task", "run_group"],
            how="inner",
        ).drop(columns=["_task"])
        return selected, "latest_per_model"

    if "run_timestamp_utc" in rows.columns:
        latest = rows.sort_values("run_timestamp_utc").iloc[-1]["run_group"]
    else:
        latest = rows.iloc[-1]["run_group"]
    return rows[rows["run_group"] == latest].copy(), str(latest)


def compute_overview(rows: pd.DataFrame) -> pd.DataFrame:
    """Compute top-level summary metrics per model across valid requests."""
    if rows.empty:
        return pd.DataFrame()

    with_s = with_series(rows)
    records = []

    for (provider, model, series), group in with_s.groupby(["provider", "model", "series"]):
        valid = group[group["valid"] == True]  # noqa: E712
        primary = valid[valid["primary_metric"].fillna(False) == True]  # noqa: E712
        reqs = group.sort_values("case_id").drop_duplicates(
            ["experiment", "case_id", "provider", "model"]
        )
        valid_reqs = reqs[reqs["valid"] == True]  # noqa: E712

        costs = (
            valid_reqs["estimated_cost_usd"].dropna()
            if "estimated_cost_usd" in valid_reqs
            else pd.Series(dtype=float)
        )
        latencies = valid_reqs["latency_ms"].dropna()

        total_count = len(reqs)
        valid_count = len(valid_reqs)
        valid_rate = (valid_count / total_count) if total_count > 0 else 0.0

        records.append(
            {
                "provider": provider,
                "model": model,
                "series": series,
                "accuracy": float(primary["correct"].mean()) if len(primary) > 0 else math.nan,
                "valid_rate": valid_rate,
                "latency_p50_ms": float(latencies.median()) if len(latencies) > 0 else math.nan,
                "latency_p95_ms": float(latencies.quantile(0.95)) if len(latencies) > 0 else math.nan,
                "cost_per_request_usd": float(costs.mean()) if len(costs) > 0 else math.nan,
                "cost_per_1k_requests_usd": float(costs.mean() * 1000) if len(costs) > 0 else 0.0,
                "run_cost_usd": float(costs.sum()) if len(costs) > 0 else 0.0,
                "requests": total_count,
                "valid_requests": valid_count,
            }
        )

    df = pd.DataFrame(records)
    if not df.empty and "accuracy" in df.columns:
        df = df.sort_values(by=["accuracy", "latency_p50_ms"], ascending=[False, True])
    return df


def compute_leaderboard(overview: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute ranked leaderboard with comparative gaps and performance badges."""
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

        # Quantization / Architecture badge
        q_label = ""
        series_lower = str(row["series"]).lower()
        if "q8_0" in series_lower or "q8" in series_lower:
            q_label = "Q8"
        elif "q4_k_m" in series_lower or "q4km" in series_lower:
            q_label = "Q4_K_M"

        # Medal icon
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"

        leaderboard.append(
            {
                "rank": rank,
                "medal": medal,
                "series": str(row["series"]),
                "model": str(row["model"]),
                "provider": str(row["provider"]),
                "accuracy": acc,
                "accuracy_pct": f"{acc * 100:.1f}%",
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
            }
        )

    return leaderboard


def compute_kpi_cards(leaderboard: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract executive summary cards from leaderboard."""
    if not leaderboard:
        return {}

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
