from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import pairwise

import numpy as np
import pandas as pd


def expected_calibration_error(correct: Iterable[int], probability: Iterable[float], bins: int = 10) -> float:
    y = np.asarray(list(correct), dtype=float)
    p = np.asarray(list(probability), dtype=float)
    if len(y) == 0:
        return math.nan
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in pairwise(edges):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return ece


def brier_score(correct: Iterable[int], probability: Iterable[float]) -> float:
    """Binary Brier score for probability assigned to the selected prediction being correct."""
    y = np.asarray(list(correct), dtype=float)
    p = np.asarray(list(probability), dtype=float)
    return float(np.mean((p - y) ** 2)) if len(y) else math.nan


def macro_f1(expected: Iterable[str], actual: Iterable[str]) -> float:
    y_true = [str(x) for x in expected]
    y_pred = [str(x) for x in actual]
    if not y_true:
        return math.nan
    labels = sorted(set(y_true))
    scores = []
    for label in labels:
        tp = sum(t == label and p == label for t, p in zip(y_true, y_pred))
        fp = sum(t != label and p == label for t, p in zip(y_true, y_pred))
        fn = sum(t == label and p != label for t, p in zip(y_true, y_pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(scores))


def wilson_interval(correct: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = correct / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    grouped = []
    for (experiment, provider, model), frame in rows.groupby(["experiment", "provider", "model"], dropna=False):
        valid = frame[frame["valid"]]
        primary = valid[valid["primary_metric"].fillna(False)]
        intermediate = valid[
            ~valid["primary_metric"].fillna(False)
            & ~valid["question_id"].isin(["__batch__", "__request__"])
        ]
        requests = valid.sort_values("case_id").drop_duplicates("case_id")

        n_primary = len(primary)
        correct_primary = int(primary["correct"].sum()) if n_primary else 0
        ci_low, ci_high = wilson_interval(correct_primary, n_primary)
        classification = primary[
            primary["expected"].notna() & primary["actual"].notna()
        ]

        grouped.append(
            {
                "experiment": experiment,
                "provider": provider,
                "model": model,
                "n_requests": int(frame["case_id"].nunique()),
                "valid_rate": float(frame.groupby("case_id")["valid"].all().mean()),
                "accuracy": float(primary["correct"].mean()) if n_primary else math.nan,
                "accuracy_ci_low": ci_low,
                "accuracy_ci_high": ci_high,
                "macro_f1": (
                    macro_f1(classification["expected"], classification["actual"])
                    if len(classification)
                    else math.nan
                ),
                "intermediate_accuracy": (
                    float(intermediate["correct"].mean()) if len(intermediate) else math.nan
                ),
                "latency_p50_ms": float(requests["latency_ms"].median()) if len(requests) else math.nan,
                "latency_p95_ms": float(requests["latency_ms"].quantile(0.95)) if len(requests) else math.nan,
                "latency_p99_ms": float(requests["latency_ms"].quantile(0.99)) if len(requests) else math.nan,
                "mean_input_tokens": (
                    float(requests["input_tokens"].dropna().mean())
                    if requests["input_tokens"].notna().any()
                    else math.nan
                ),
                "mean_cached_input_tokens": (
                    float(requests["cached_input_tokens"].dropna().mean())
                    if "cached_input_tokens" in requests
                    and requests["cached_input_tokens"].notna().any()
                    else math.nan
                ),
                "mean_output_tokens": (
                    float(requests["output_tokens"].dropna().mean())
                    if requests["output_tokens"].notna().any()
                    else math.nan
                ),
                "cost_per_request_usd": (
                    float(requests["estimated_cost_usd"].dropna().mean())
                    if "estimated_cost_usd" in requests
                    and requests["estimated_cost_usd"].notna().any()
                    else math.nan
                ),
                "cost_per_1k_requests_usd": (
                    float(requests["estimated_cost_usd"].dropna().mean()) * 1000
                    if "estimated_cost_usd" in requests
                    and requests["estimated_cost_usd"].notna().any()
                    else math.nan
                ),
                "run_cost_usd": (
                    float(requests["estimated_cost_usd"].dropna().sum())
                    if "estimated_cost_usd" in requests
                    and requests["estimated_cost_usd"].notna().any()
                    else math.nan
                ),
            }
        )
    return pd.DataFrame(grouped)


def _calibration_rows(rows: pd.DataFrame) -> pd.DataFrame:
    return rows[
        rows["experiment"].astype(str).str.startswith("02-calibration")
        & rows["valid"]
        & rows["primary_metric"].fillna(False)
    ].copy()


def calibration_summary(rows: pd.DataFrame) -> pd.DataFrame:
    data = []
    subset = _calibration_rows(rows)
    subset = subset[subset["predicted_probability"].notna()]
    for (provider, model), frame in subset.groupby(["provider", "model"]):
        data.append(
            {
                "provider": provider,
                "model": model,
                "n": len(frame),
                "ece_probability": expected_calibration_error(
                    frame["correct"].astype(int), frame["predicted_probability"]
                ),
                "brier_probability": brier_score(
                    frame["correct"].astype(int), frame["predicted_probability"]
                ),
                "mean_predicted_probability": float(frame["predicted_probability"].mean()),
                "mean_confidence": (
                    float(frame["confidence"].dropna().mean())
                    if frame["confidence"].notna().any()
                    else math.nan
                ),
            }
        )
    return pd.DataFrame(data)


def reliability_bins(rows: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    records = []
    subset = _calibration_rows(rows)
    subset = subset[subset["predicted_probability"].notna()].copy()
    subset["bin"] = pd.cut(
        subset["predicted_probability"],
        np.linspace(0, 1, bins + 1),
        include_lowest=True,
    )
    for (provider, model, interval), frame in subset.groupby(
        ["provider", "model", "bin"], observed=True
    ):
        records.append(
            {
                "provider": provider,
                "model": model,
                "predicted_probability": float(frame["predicted_probability"].mean()),
                "accuracy": float(frame["correct"].mean()),
                "count": len(frame),
            }
        )
    return pd.DataFrame(records)


def coverage_curve(rows: pd.DataFrame) -> pd.DataFrame:
    """Selective automation using each provider's native confidence score."""
    records = []
    subset = _calibration_rows(rows)
    subset = subset[subset["confidence"].notna()]
    for (provider, model), frame in subset.groupby(["provider", "model"]):
        for threshold in np.linspace(0.0, 1.0, 21):
            accepted = frame[frame["confidence"] >= threshold]
            records.append(
                {
                    "provider": provider,
                    "model": model,
                    "threshold": threshold,
                    "coverage": len(accepted) / len(frame) if len(frame) else 0,
                    "accuracy": float(accepted["correct"].mean()) if len(accepted) else math.nan,
                }
            )
    return pd.DataFrame(records)


def difficulty_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if "difficulty" not in rows.columns:
        return pd.DataFrame()
    subset = _calibration_rows(rows)
    subset = subset[subset["difficulty"].notna()]
    if subset.empty:
        return pd.DataFrame()
    return (
        subset.groupby(["provider", "model", "difficulty"], as_index=False)
        .agg(
            accuracy=("correct", "mean"),
            n=("case_id", "nunique"),
            mean_confidence=("confidence", "mean"),
            mean_predicted_probability=("predicted_probability", "mean"),
        )
    )


def top_confusions(rows: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    subset = rows[
        rows["valid"]
        & rows["primary_metric"].fillna(False)
        & rows["expected"].notna()
        & rows["actual"].notna()
        & ~rows["correct"]
    ].copy()
    if subset.empty:
        return pd.DataFrame()
    grouped = (
        subset.groupby(["provider", "model", "expected", "actual"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    grouped["pair"] = grouped["expected"].astype(str) + " → " + grouped["actual"].astype(str)
    return (
        grouped.sort_values(["provider", "model", "count"], ascending=[True, True, False])
        .groupby(["provider", "model"], as_index=False, group_keys=False)
        .head(limit)
    )
