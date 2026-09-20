from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io import to_html

from jev_bench.metrics import calibration_summary, reliability_bins, summarize


def _chart_html(fig) -> str:
    return to_html(fig, full_html=False, include_plotlyjs=False, config={"displaylogo": False})


def build_report(raw_csv: Path, output_html: Path) -> None:
    rows = pd.read_csv(raw_csv)
    summary = summarize(rows)
    cal = calibration_summary(rows)
    rel = reliability_bins(rows)

    comparable = summary[~summary["experiment"].eq("03-parallel-scaling")].copy()
    acc = px.bar(
        comparable,
        x="experiment",
        y="accuracy",
        color="provider",
        barmode="group",
        range_y=[0, 1],
        title="Accuracy by experiment",
        text_auto=".1%",
    )
    latency = px.bar(
        summary,
        x="experiment",
        y="latency_p50_ms",
        color="provider",
        barmode="group",
        title="Median end-to-end latency",
        labels={"latency_p50_ms": "p50 latency (ms)"},
    )
    scatter = px.scatter(
        comparable,
        x="latency_p50_ms",
        y="accuracy",
        color="provider",
        text="experiment",
        title="Accuracy vs latency — upper-left is better",
        labels={"latency_p50_ms": "p50 latency (ms)", "accuracy": "accuracy"},
    )
    scaling = rows[rows["experiment"].eq("03-parallel-scaling") & rows["valid"]].copy()
    scaling_fig = px.line(
        scaling.groupby(["provider", "question_count"], as_index=False)["latency_ms"].median(),
        x="question_count",
        y="latency_ms",
        color="provider",
        markers=True,
        title="Parallel decision scaling",
        labels={"question_count": "questions in one request", "latency_ms": "median latency (ms)"},
    )
    rel_fig = go.Figure()
    rel_fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="perfect calibration"))
    for provider, frame in rel.groupby("provider"):
        rel_fig.add_trace(
            go.Scatter(
                x=frame["confidence"],
                y=frame["accuracy"],
                mode="lines+markers",
                name=provider,
                text=[f"n={n}" for n in frame["count"]],
            )
        )
    rel_fig.update_layout(
        title="Reliability diagram",
        xaxis_title="reported confidence",
        yaxis_title="observed accuracy",
        xaxis_range=[0, 1],
        yaxis_range=[0, 1],
    )

    cards = []
    for _, row in comparable.iterrows():
        cards.append(
            f"<div class='card'><div class='eyebrow'>{row['experiment']} · {row['provider']}</div>"
            f"<div class='metric'>{row['accuracy']:.1%}</div><div>accuracy</div>"
            f"<div class='sub'>{row['latency_p50_ms']:.0f} ms p50 · {row['latency_p95_ms']:.0f} ms p95</div></div>"
        )

    calibration_table = cal.to_html(index=False, float_format=lambda x: f"{x:.4f}") if not cal.empty else "<p>No calibration data.</p>"
    summary_table = summary.to_html(index=False, float_format=lambda x: f"{x:.3f}")
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Jev vs LLM benchmark</title><script src='https://cdn.plot.ly/plotly-3.1.0.min.js'></script>
<style>
body{{font-family:Inter,system-ui,sans-serif;margin:0;background:#f6f7f9;color:#111827}}
main{{max-width:1280px;margin:auto;padding:32px 20px 64px}} h1{{font-size:40px;margin-bottom:6px}}
.lead{{color:#4b5563;max-width:900px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:24px 0}}
.card,.panel{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:18px;box-shadow:0 1px 2px #00000008}}
.metric{{font-size:34px;font-weight:750;margin-top:8px}} .eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280}}
.sub{{font-size:13px;color:#6b7280;margin-top:8px}} .panel{{margin:14px 0}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{padding:8px;border-bottom:1px solid #eee;text-align:left}}
.notice{{background:#fff7ed;border:1px solid #fed7aa;padding:14px;border-radius:12px;margin:18px 0}}
</style></head><body><main>
<h1>Jev vs LLM</h1><p class='lead'>Decision-model benchmark: correctness, calibration, latency, parallel scaling and workflow outcomes. Numbers reflect this run and its configured models, region and network path.</p>
<div class='notice'><b>Publication note:</b> verify the TypeSafe terms applicable to your account before publishing Jev performance numbers. Raw results are gitignored by default.</div>
<div class='grid'>{''.join(cards)}</div>
<div class='panel'>{_chart_html(acc)}</div><div class='panel'>{_chart_html(latency)}</div>
<div class='panel'>{_chart_html(scatter)}</div><div class='panel'>{_chart_html(scaling_fig)}</div>
<div class='panel'>{_chart_html(rel_fig)}</div>
<div class='panel'><h2>Calibration metrics</h2>{calibration_table}</div>
<div class='panel'><h2>Aggregate metrics</h2>{summary_table}</div>
</main></body></html>"""
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
