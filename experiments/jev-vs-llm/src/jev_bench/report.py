from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io import to_html

from jev_bench.metrics import (
    calibration_summary,
    coverage_curve,
    difficulty_summary,
    reliability_bins,
    summarize,
    top_confusions,
)


def _chart_html(fig) -> str:
    return to_html(fig, full_html=False, include_plotlyjs=False, config={"displaylogo": False})


def _select_run_group(rows: pd.DataFrame, run_group: str | None) -> tuple[pd.DataFrame, str | None]:
    if "run_group" not in rows.columns:
        return rows, None
    if run_group:
        selected = rows[rows["run_group"] == run_group].copy()
        if selected.empty:
            raise ValueError(f"run_group not found: {run_group}")
        return selected, run_group
    if "run_timestamp_utc" in rows.columns:
        latest = rows.sort_values("run_timestamp_utc").iloc[-1]["run_group"]
    else:
        latest = rows.iloc[-1]["run_group"]
    return rows[rows["run_group"] == latest].copy(), str(latest)


def _empty_chart(title: str):
    fig = go.Figure()
    fig.update_layout(title=title)
    return fig


def build_report(raw_csv: Path, output_html: Path, run_group: str | None = None) -> None:
    all_rows = pd.read_csv(raw_csv)
    rows, selected_group = _select_run_group(all_rows, run_group)
    summary = summarize(rows)
    cal = calibration_summary(rows)
    rel = reliability_bins(rows)
    coverage = coverage_curve(rows)
    difficulty = difficulty_summary(rows)
    confusions = top_confusions(rows, limit=12)

    comparable = summary[summary["accuracy"].notna()].copy()
    if not comparable.empty:
        comparable["err_plus"] = comparable["accuracy_ci_high"] - comparable["accuracy"]
        comparable["err_minus"] = comparable["accuracy"] - comparable["accuracy_ci_low"]
        acc = px.bar(
            comparable,
            x="experiment",
            y="accuracy",
            color="provider",
            barmode="group",
            range_y=[0, 1],
            title="Primary outcome accuracy (95% Wilson interval)",
            text_auto=".1%",
            error_y="err_plus",
            error_y_minus="err_minus",
            hover_data=["macro_f1", "n_requests", "valid_rate"],
        )
        scatter = px.scatter(
            comparable,
            x="latency_p50_ms",
            y="accuracy",
            color="provider",
            symbol="experiment",
            text="experiment",
            title="Accuracy vs latency — upper-left is better",
            labels={"latency_p50_ms": "p50 latency (ms)", "accuracy": "primary accuracy"},
            hover_data=["macro_f1", "latency_p95_ms", "valid_rate"],
        )
    else:
        acc = _empty_chart("Primary outcome accuracy — no data")
        scatter = _empty_chart("Accuracy vs latency — no data")

    latency = px.bar(
        summary,
        x="experiment",
        y="latency_p50_ms",
        color="provider",
        barmode="group",
        title="Median end-to-end request latency",
        labels={"latency_p50_ms": "p50 latency (ms)"},
        hover_data=["latency_p95_ms", "latency_p99_ms", "n_requests"],
    )

    scaling = rows[rows["experiment"].eq("03-parallel-scaling") & rows["valid"]].copy()
    if not scaling.empty:
        scaling_data = (
            scaling.groupby(["provider", "question_count"], as_index=False)
            .agg(
                latency_p50_ms=("latency_ms", "median"),
                latency_p95_ms=("latency_ms", lambda x: x.quantile(0.95)),
            )
        )
        scaling_fig = px.line(
            scaling_data,
            x="question_count",
            y="latency_p50_ms",
            color="provider",
            markers=True,
            title="Parallel decision scaling: 1 → 32 questions in one request",
            labels={
                "question_count": "questions in one request",
                "latency_p50_ms": "median latency (ms)",
            },
            hover_data=["latency_p95_ms"],
        )
    else:
        scaling_fig = _empty_chart("Parallel decision scaling — no data")

    rel_fig = go.Figure()
    rel_fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="perfect calibration",
            line={"dash": "dash"},
        )
    )
    for provider, frame in rel.groupby("provider"):
        rel_fig.add_trace(
            go.Scatter(
                x=frame["predicted_probability"],
                y=frame["accuracy"],
                mode="lines+markers",
                name=provider,
                text=[f"n={n}" for n in frame["count"]],
            )
        )
    rel_fig.update_layout(
        title="Probability calibration: predicted-class probability vs observed accuracy",
        xaxis_title="probability assigned to selected class",
        yaxis_title="observed accuracy",
        xaxis_range=[0, 1],
        yaxis_range=[0, 1],
    )

    if not coverage.empty:
        coverage_fig = px.line(
            coverage,
            x="coverage",
            y="accuracy",
            color="provider",
            markers=True,
            title="Selective automation using native confidence",
            labels={
                "coverage": "share of cases auto-accepted",
                "accuracy": "accuracy among accepted cases",
            },
            range_x=[0, 1],
            range_y=[0, 1],
            hover_data=["threshold"],
        )
    else:
        coverage_fig = _empty_chart("Accuracy vs coverage — no data")

    if not difficulty.empty:
        difficulty_fig = px.bar(
            difficulty,
            x="difficulty",
            y="accuracy",
            color="provider",
            barmode="group",
            range_y=[0, 1],
            title="Calibration benchmark by scope",
            text_auto=".1%",
            hover_data=["n", "mean_confidence", "mean_predicted_probability"],
        )
    else:
        difficulty_fig = _empty_chart("Calibration benchmark by scope — no data")

    if not confusions.empty:
        confusions_fig = px.bar(
            confusions.sort_values("count"),
            x="count",
            y="pair",
            color="provider",
            orientation="h",
            barmode="group",
            title="Most frequent confusion pairs",
            labels={"pair": "expected → predicted", "count": "errors"},
        )
    else:
        confusions_fig = _empty_chart("Confusion pairs — no classification errors")

    cards = []
    for _, row in comparable.iterrows():
        f1 = f"{row['macro_f1']:.1%}" if pd.notna(row["macro_f1"]) else "—"
        cards.append(
            f"<div class='card'><div class='eyebrow'>{row['experiment']} · {row['provider']}</div>"
            f"<div class='metric'>{row['accuracy']:.1%}</div><div>accuracy · F1 {f1}</div>"
            f"<div class='sub'>{row['latency_p50_ms']:.0f} ms p50 · "
            f"{row['latency_p95_ms']:.0f} ms p95 · n={int(row['n_requests'])}</div></div>"
        )

    calibration_table = (
        cal.to_html(index=False, float_format=lambda x: f"{x:.4f}")
        if not cal.empty
        else "<p>No calibration data.</p>"
    )
    summary_table = summary.to_html(index=False, float_format=lambda x: f"{x:.4f}")
    group_text = selected_group or "legacy / ungrouped"
    suite = (
        ", ".join(sorted(rows["suite"].dropna().astype(str).unique()))
        if "suite" in rows.columns
        else "unspecified"
    )
    locations = (
        ", ".join(sorted(rows["runner_location"].dropna().astype(str).unique()))
        if "runner_location" in rows.columns
        else "unspecified"
    )

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Jev vs LLM benchmark</title><script src='https://cdn.plot.ly/plotly-3.1.0.min.js'></script>
<style>
body{{font-family:Inter,system-ui,sans-serif;margin:0;background:#f6f7f9;color:#111827}}
main{{max-width:1280px;margin:auto;padding:32px 20px 64px}}
h1{{font-size:40px;margin:0 0 6px}} h2{{margin-top:4px}}
.lead{{color:#4b5563;max-width:960px;line-height:1.55}}
.meta{{font-size:13px;color:#6b7280;margin-top:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:24px 0}}
.card,.panel{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:18px;box-shadow:0 1px 2px #00000008}}
.metric{{font-size:34px;font-weight:750;margin-top:8px}}
.eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280}}
.sub{{font-size:13px;color:#6b7280;margin-top:8px}}
.panel{{margin:14px 0;overflow:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:8px;border-bottom:1px solid #eee;text-align:left}}
.notice{{background:#fff7ed;border:1px solid #fed7aa;padding:14px;border-radius:12px;margin:18px 0}}
code{{background:#eef2f7;padding:2px 5px;border-radius:5px}}
</style></head><body><main>
<h1>Jev vs LLM</h1>
<p class='lead'>Decision benchmark across correctness, calibration, latency and scaling. Accuracy and latency are deliberately shown together: a faster model that makes materially more mistakes is not automatically a better decision layer, and vice versa.</p>
<div class='meta'>Run group: <code>{group_text}</code> · suite: <code>{suite}</code> · runner: <code>{locations}</code></div>
<div class='notice'><b>Publication note:</b> verify the TypeSafe terms applicable to your account before publishing Jev performance numbers. Raw results are gitignored by default.</div>
<div class='grid'>{''.join(cards)}</div>
<div class='panel'>{_chart_html(acc)}</div>
<div class='panel'>{_chart_html(latency)}</div>
<div class='panel'>{_chart_html(scatter)}</div>
<div class='panel'>{_chart_html(rel_fig)}</div>
<div class='panel'>{_chart_html(coverage_fig)}</div>
<div class='panel'>{_chart_html(difficulty_fig)}</div>
<div class='panel'>{_chart_html(confusions_fig)}</div>
<div class='panel'>{_chart_html(scaling_fig)}</div>
<div class='panel'><h2>Calibration metrics</h2>{calibration_table}</div>
<div class='panel'><h2>Aggregate metrics</h2>{summary_table}</div>
</main></body></html>"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
