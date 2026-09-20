from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd


def expected_calibration_error(correct: Iterable[int], confidence: Iterable[float], bins: int = 10) -> float:
    y = np.asarray(list(correct), dtype=float)
    c = np.asarray(list(confidence), dtype=float)
    if len(y) == 0:
        return math.nan
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (c >= lo) & (c < hi if hi < 1.0 else c <= hi)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(c[mask].mean()))
    return ece


def brier_score(correct: Iterable[int], confidence: Iterable[float]) -> float:
    """Binary Brier score for the reported confidence of the selected answer."""
    y = np.asarray(list(correct), dtype=float)
    c = np.asarray(list(confidence), dtype=float)
    return float(np.mean((c - y) ** 2)) if len(y) else math.nan


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
        grouped.append(
            {
                "experiment": experiment,
                "provider": provider,
                "model": model,
                "n_requests": int(frame["case_id"].nunique()),
                "valid_rate": float(frame.groupby("case_id")["valid"].all().mean()),
                "accuracy": float(primary["correct"].mean()) if len(primary) else math.nan,
                "intermediate_accuracy": float(intermediate["correct"].mean()) if len(intermediate) else math.nan,
                "latency_p50_ms": float(requests["latency_ms"].median()) if len(requests) else math.nan,
                "latency_p95_ms": float(requests["latency_ms"].quantile(0.95)) if len(requests) else math.nan,
                "latency_p99_ms": float(requests["latency_ms"].quantile(0.99)) if len(requests) else math.nan,
                "mean_input_tokens": float(requests["input_tokens"].dropna().mean()) if requests["input_tokens"].notna().any() else math.nan,
                "mean_output_tokens": float(requests["output_tokens"].dropna().mean()) if requests["output_tokens"].notna().any() else math.nan,
            }
        )
    return pd.DataFrame(grouped)


def calibration_summary(rows: pd.DataFrame) -> pd.DataFrame:
    data = []
    subset = rows[
        (rows["experiment"] == "02-calibration")
        & rows["valid"]
        & rows["primary_metric"].fillna(False)
        & rows["confidence"].notna()
    ]
    for (provider, model), frame in subset.groupby(["provider", "model"]):
        data.append(
            {
                "provider": provider,
                "model": model,
                "ece": expected_calibration_error(frame["correct"].astype(int), frame["confidence"]),
                "confidence_brier": brier_score(frame["correct"].astype(int), frame["confidence"]),
            }
        )
    return pd.DataFrame(data)


def reliability_bins(rows: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    records = []
    subset = rows[
        (rows["experiment"] == "02-calibration")
        & rows["valid"]
        & rows["primary_metric"].fillna(False)
        & rows["confidence"].notna()
    ].copy()
    subset["bin"] = pd.cut(subset["confidence"], np.linspace(0, 1, bins + 1), include_lowest=True)
    for (provider, interval), frame in subset.groupby(["provider", "bin"], observed=True):
        records.append(
            {
                "provider": provider,
                "confidence": float(frame["confidence"].mean()),
                "accuracy": float(frame["correct"].mean()),
                "count": len(frame),
            }
        )
    return pd.DataFrame(records)


def coverage_curve(rows: pd.DataFrame) -> pd.DataFrame:
    records = []
    subset = rows[
        (rows["experiment"] == "02-calibration")
        & rows["valid"]
        & rows["primary_metric"].fillna(False)
        & rows["confidence"].notna()
    ]
    for provider, frame in subset.groupby("provider"):
        for threshold in np.linspace(0.0, 1.0, 21):
            accepted = frame[frame["confidence"] >= threshold]
            records.append(
                {
                    "provider": provider,
                    "threshold": threshold,
                    "coverage": len(accepted) / len(frame) if len(frame) else 0,
                    "accuracy": float(accepted["correct"].mean()) if len(accepted) else math.nan,
                }
            )
    return pd.DataFrame(records)
