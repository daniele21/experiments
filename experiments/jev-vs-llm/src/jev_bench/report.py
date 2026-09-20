from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io import to_html

from jev_bench.costs import pricing_metadata
from jev_bench.metrics import (
    calibration_summary,
    coverage_curve,
    difficulty_summary,
    reliability_bins,
    summarize,
    top_confusions,
)


def _series_name(provider: str, model: str) -> str:
    if provider == "jev":
        return f"Jev · {model}"
    if provider == "llm-monolithic":
        return f"{model} · monolithic"
    if provider == "local-korgis":
        labels = {
            "qwen3.5-4b-q4km": "Korgis · Qwen3.5 4B Q4_K_M",
            "qwen3.5-9b-q4km": "Korgis · Qwen3.5 9B Q4_K_M",
            "nemotron-nano-4b": "Korgis · Nemotron Nano 4B Q4_K_M",
        }
        return labels.get(model, f"Korgis · {model}")
    return model


def _with_series(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["series"] = [
        _series_name(str(provider), str(model))
        for provider, model in zip(frame["provider"], frame["model"], strict=False)
    ]
    return frame


def _tag_figure(fig, series_names: list[str]):
    for trace in fig.data:
        name = str(getattr(trace, "name", "") or "")
        matched = next((series for series in series_names if series in name), None)
        trace.meta = {"series": matched} if matched else {"series": None}
    return fig


def _chart_html(fig, series_names: list[str]) -> str:
    _tag_figure(fig, series_names)
    return to_html(fig, full_html=False, include_plotlyjs=False, config={"displaylogo": False})


def _empty_chart(title: str):
    fig = go.Figure()
    fig.update_layout(title=title)
    return fig


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


def _money(value: float | None, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if value == 0:
        return "$0"
    if abs(value) < 0.01:
        return f"${value:.6f}"
    return f"${value:.{digits}f}"


def _overview(rows: pd.DataFrame) -> pd.DataFrame:
    valid = _with_series(rows[rows["valid"]].copy())
    primary = valid[valid["primary_metric"].fillna(False)]
    requests = valid.sort_values("case_id").drop_duplicates(
        ["experiment", "case_id", "provider", "model"]
    )

    records = []
    for (provider, model, series), req in requests.groupby(["provider", "model", "series"]):
        prim = primary[(primary["provider"] == provider) & (primary["model"] == model)]
        costs = (
            req["estimated_cost_usd"].dropna()
            if "estimated_cost_usd" in req
            else pd.Series(dtype=float)
        )
        records.append(
            {
                "provider": provider,
                "model": model,
                "series": series,
                "accuracy": float(prim["correct"].mean()) if len(prim) else math.nan,
                "latency_p50_ms": float(req["latency_ms"].median()) if len(req) else math.nan,
                "latency_p95_ms": float(req["latency_ms"].quantile(0.95)) if len(req) else math.nan,
                "cost_per_request_usd": float(costs.mean()) if len(costs) else math.nan,
                "cost_per_1k_requests_usd": float(costs.mean()) * 1000 if len(costs) else math.nan,
                "run_cost_usd": float(costs.sum()) if len(costs) else math.nan,
                "requests": len(req),
            }
        )
    return pd.DataFrame(records)


def _experiment_summary(summary: pd.DataFrame, experiment: str) -> pd.DataFrame:
    return summary[summary["experiment"].eq(experiment)].copy()


def _summary_accuracy_chart(frame: pd.DataFrame, title: str):
    frame = frame[frame["accuracy"].notna()].copy() if not frame.empty else frame
    if frame.empty:
        return _empty_chart(f"{title} — no data")
    frame["err_plus"] = frame["accuracy_ci_high"] - frame["accuracy"]
    frame["err_minus"] = frame["accuracy"] - frame["accuracy_ci_low"]
    return px.bar(
        frame,
        x="series",
        y="accuracy",
        color="series",
        range_y=[0, 1],
        title=title,
        text_auto=".1%",
        error_y="err_plus",
        error_y_minus="err_minus",
        hover_data=["macro_f1", "n_requests", "valid_rate"],
        labels={"series": "model", "accuracy": "accuracy"},
    )


def _summary_latency_chart(frame: pd.DataFrame, title: str):
    if frame.empty:
        return _empty_chart(f"{title} — no data")
    return px.bar(
        frame,
        x="series",
        y="latency_p50_ms",
        color="series",
        title=title,
        labels={"series": "model", "latency_p50_ms": "p50 latency (ms)"},
        hover_data=["latency_p95_ms", "latency_p99_ms", "n_requests"],
    )


def _summary_cost_chart(frame: pd.DataFrame, title: str):
    if frame.empty or "cost_per_1k_requests_usd" not in frame:
        return _empty_chart(f"{title} — no data")
    data = frame[frame["cost_per_1k_requests_usd"].notna()].copy()
    if data.empty:
        return _empty_chart(f"{title} — pricing unavailable")
    return px.bar(
        data,
        x="series",
        y="cost_per_1k_requests_usd",
        color="series",
        title=title,
        labels={"series": "model", "cost_per_1k_requests_usd": "API USD / 1,000 requests"},
        hover_data=["cost_per_request_usd", "run_cost_usd", "mean_input_tokens", "mean_output_tokens"],
    )


def _model_cards(overview: pd.DataFrame) -> str:
    cards = []
    for _, row in overview.sort_values(["provider", "model"]).iterrows():
        accuracy = f"{row['accuracy']:.1%}" if pd.notna(row["accuracy"]) else "—"
        latency = f"{row['latency_p50_ms']:.0f} ms" if pd.notna(row["latency_p50_ms"]) else "—"
        cost = _money(row["cost_per_1k_requests_usd"], digits=3)
        cards.append(
            f"<article class='model-card' data-series={json.dumps(str(row['series']))}>"
            f"<div class='model-name'>{row['series']}</div>"
            "<div class='metric-row'>"
            f"<div><span>Accuracy</span><strong>{accuracy}</strong></div>"
            f"<div><span>p50</span><strong>{latency}</strong></div>"
            f"<div><span>API cost / 1k</span><strong>{cost}</strong></div>"
            "</div>"
            f"<div class='card-foot'>{int(row['requests'])} measured requests · run cost {_money(row['run_cost_usd'])}</div>"
            "</article>"
        )
    return "".join(cards)


def _plot_block(title: str, description: str, fig, series_names: list[str]) -> str:
    return (
        "<section class='plot-card'>"
        f"<div class='plot-copy'><h3>{title}</h3><p>{description}</p></div>"
        f"{_chart_html(fig, series_names)}"
        "</section>"
    )


def build_report(raw_csv: Path, output_html: Path, run_group: str | None = None) -> None:
    all_rows = pd.read_csv(raw_csv)
    rows, selected_group = _select_run_group(all_rows, run_group)
    summary = _with_series(summarize(rows))
    overview = _overview(rows)

    cal = calibration_summary(rows)
    if not cal.empty:
        cal = _with_series(cal)
    rel = reliability_bins(rows)
    coverage = coverage_curve(rows)
    difficulty = difficulty_summary(rows)
    confusions = top_confusions(rows, limit=12)

    series_names = (
        list(dict.fromkeys(overview["series"].dropna().astype(str).tolist()))
        if not overview.empty
        else []
    )

    comparable = overview[overview["accuracy"].notna()].copy()
    if not comparable.empty:
        accuracy_latency = px.scatter(
            comparable,
            x="latency_p50_ms",
            y="accuracy",
            color="series",
            text="series",
            title="Accuracy vs latency",
            labels={"latency_p50_ms": "p50 latency (ms)", "accuracy": "accuracy"},
            hover_data=["cost_per_1k_requests_usd", "latency_p95_ms", "requests"],
            range_y=[0, 1],
        )
        priced = comparable[comparable["cost_per_1k_requests_usd"].notna()].copy()
        cost_accuracy = (
            px.scatter(
                priced,
                x="cost_per_1k_requests_usd",
                y="accuracy",
                color="series",
                text="series",
                title="Accuracy vs API cost",
                labels={"cost_per_1k_requests_usd": "API USD / 1,000 requests", "accuracy": "accuracy"},
                hover_data=["latency_p50_ms", "run_cost_usd", "requests"],
                range_y=[0, 1],
            )
            if not priced.empty
            else _empty_chart("Accuracy vs API cost — pricing unavailable")
        )
    else:
        accuracy_latency = _empty_chart("Accuracy vs latency — no data")
        cost_accuracy = _empty_chart("Accuracy vs API cost — no data")

    routing = _experiment_summary(summary, "01-routing-public")
    if routing.empty:
        routing = _experiment_summary(summary, "01-routing")

    routing_accuracy = _summary_accuracy_chart(routing, "Routing accuracy")
    routing_latency = _summary_latency_chart(routing, "Routing latency")
    routing_cost = _summary_cost_chart(routing, "Routing API cost")

    if not confusions.empty:
        confusions = _with_series(confusions)
        confusion_fig = px.bar(
            confusions.sort_values("count"),
            x="count",
            y="pair",
            color="series",
            orientation="h",
            title="Most frequent confusion pairs",
            labels={"pair": "expected → predicted", "count": "errors"},
        )
    else:
        confusion_fig = _empty_chart("Most frequent confusion pairs — no classification errors")

    rel_fig = go.Figure()
    rel_fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Perfect calibration",
            line={"dash": "dash"},
            meta={"series": None},
        )
    )
    if not rel.empty:
        rel = _with_series(rel)
        for series, frame in rel.groupby("series"):
            rel_fig.add_trace(
                go.Scatter(
                    x=frame["predicted_probability"],
                    y=frame["accuracy"],
                    mode="lines+markers",
                    name=series,
                    meta={"series": series},
                    text=[f"n={n}" for n in frame["count"]],
                )
            )
    rel_fig.update_layout(
        title="Probability calibration",
        xaxis_title="probability assigned to selected class",
        yaxis_title="observed accuracy",
        xaxis_range=[0, 1],
        yaxis_range=[0, 1],
    )

    if not coverage.empty:
        coverage = _with_series(coverage)
        coverage_fig = px.line(
            coverage,
            x="coverage",
            y="accuracy",
            color="series",
            markers=True,
            title="Selective automation",
            labels={"coverage": "share auto-accepted", "accuracy": "accuracy among accepted"},
            range_x=[0, 1],
            range_y=[0, 1],
            hover_data=["threshold"],
        )
    else:
        coverage_fig = _empty_chart("Selective automation — no data")

    if not difficulty.empty:
        difficulty = _with_series(difficulty)
        difficulty_fig = px.bar(
            difficulty,
            x="difficulty",
            y="accuracy",
            color="series",
            barmode="group",
            range_y=[0, 1],
            title="In-scope vs out-of-scope",
            text_auto=".1%",
            hover_data=["n", "mean_confidence", "mean_predicted_probability"],
        )
    else:
        difficulty_fig = _empty_chart("In-scope vs out-of-scope — no data")

    scaling = rows[rows["experiment"].eq("03-parallel-scaling") & rows["valid"]].copy()
    if not scaling.empty:
        scaling = _with_series(scaling)
        scaling_data = (
            scaling.groupby(["series", "question_count"], as_index=False)
            .agg(
                latency_p50_ms=("latency_ms", "median"),
                latency_p95_ms=("latency_ms", lambda x: x.quantile(0.95)),
                cost_per_request_usd=("estimated_cost_usd", "mean"),
            )
        )
        scaling_fig = px.line(
            scaling_data,
            x="question_count",
            y="latency_p50_ms",
            color="series",
            markers=True,
            title="Parallel decision scaling",
            labels={"question_count": "questions in one request", "latency_p50_ms": "p50 latency (ms)"},
            hover_data=["latency_p95_ms", "cost_per_request_usd"],
        )
        scaling_cost_fig = px.line(
            scaling_data,
            x="question_count",
            y="cost_per_request_usd",
            color="series",
            markers=True,
            title="API cost while adding decisions",
            labels={"question_count": "questions in one request", "cost_per_request_usd": "USD / request"},
        )
    else:
        scaling_fig = _empty_chart("Parallel decision scaling — no data")
        scaling_cost_fig = _empty_chart("API cost while adding decisions — no data")

    workflow = _experiment_summary(summary, "04-workflow")
    agent = _experiment_summary(summary, "05-hybrid-agent")

    pricing = pricing_metadata()
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
    group_text = selected_group or "legacy / ungrouped"
    model_chips = "".join(
        f"<button class='model-chip active' data-series={json.dumps(series)}>{series}</button>"
        for series in series_names
    )

    calibration_table = (
        cal[
            [
                "series",
                "n",
                "ece_probability",
                "brier_probability",
                "mean_predicted_probability",
                "mean_confidence",
            ]
        ].to_html(index=False, float_format=lambda x: f"{x:.4f}")
        if not cal.empty
        else "<p class='empty'>No calibration data in this run.</p>"
    )

    summary_columns = [
        "experiment",
        "series",
        "accuracy",
        "macro_f1",
        "latency_p50_ms",
        "latency_p95_ms",
        "cost_per_1k_requests_usd",
        "run_cost_usd",
        "valid_rate",
    ]
    summary_table = summary[[c for c in summary_columns if c in summary.columns]].to_html(
        index=False,
        float_format=lambda x: f"{x:.6f}",
    )

    overview_html = (
        "<div class='model-grid'>" + _model_cards(overview) + "</div>"
        + _plot_block(
            "Accuracy vs latency",
            "Upper-left is preferable: higher correctness with lower end-to-end latency. Hover to inspect cost and p95.",
            accuracy_latency,
            series_names,
        )
        + _plot_block(
            "Accuracy vs API cost",
            "Upper-left is preferable: higher correctness at lower estimated standard API cost.",
            cost_accuracy,
            series_names,
        )
    )

    routing_html = (
        _plot_block(
            "Routing accuracy",
            "77-way intent classification. Bars include a 95% Wilson interval; macro-F1 is available on hover.",
            routing_accuracy,
            series_names,
        )
        + _plot_block(
            "Routing latency",
            "Client-observed p50 latency. p95 and p99 are available on hover.",
            routing_latency,
            series_names,
        )
        + _plot_block(
            "Routing API cost",
            "Estimated list-price cost for 1,000 requests using the pricing snapshot recorded with the run.",
            routing_cost,
            series_names,
        )
        + _plot_block(
            "Most frequent confusion pairs",
            "Where models disagree most often with the labelled intent. Use this to understand the quality gap, not only the aggregate score.",
            confusion_fig,
            series_names,
        )
    )

    calibration_html = (
        _plot_block(
            "Probability calibration",
            "If a selected answer receives probability 0.8, it should be correct roughly 80% of the time. The dashed diagonal is ideal calibration.",
            rel_fig,
            series_names,
        )
        + _plot_block(
            "Selective automation",
            "As the confidence threshold rises, coverage falls. The useful question is how much traffic can be automated at a required accuracy.",
            coverage_fig,
            series_names,
        )
        + _plot_block(
            "In-scope vs out-of-scope",
            "Separates supported BANKING77 requests from filtered CLINC150 OOS requests mapped to other.",
            difficulty_fig,
            series_names,
        )
        + f"<section class='table-card'><div class='plot-copy'><h3>Calibration metrics</h3><p>ECE and Brier use selected-class probability; native confidence is kept separate.</p></div>{calibration_table}</section>"
    )

    scaling_html = (
        _plot_block(
            "Parallel decision scaling",
            "Same state, increasing independent questions from 1 to 32 in one request.",
            scaling_fig,
            series_names,
        )
        + _plot_block(
            "API cost while adding decisions",
            "Shows how estimated request cost changes as the number of independent decisions grows.",
            scaling_cost_fig,
            series_names,
        )
    )

    workflow_html = (
        _plot_block(
            "Final workflow accuracy",
            "Primary metric is the deterministic workflow's final action. Intermediate judgments remain diagnostic.",
            _summary_accuracy_chart(workflow, "Deterministic workflow accuracy"),
            series_names,
        )
        + _plot_block(
            "Workflow latency",
            "Compares typed/decomposed workflows with monolithic LLM policy execution.",
            _summary_latency_chart(workflow, "Deterministic workflow latency"),
            series_names,
        )
        + _plot_block(
            "Workflow API cost",
            "Estimated list-price cost for 1,000 workflow requests.",
            _summary_cost_chart(workflow, "Deterministic workflow cost"),
            series_names,
        )
    )

    agent_html = (
        _plot_block(
            "Agent decision accuracy",
            "Measures routing and escalation quality before any natural-language generation step is added.",
            _summary_accuracy_chart(agent, "Hybrid agent decision accuracy"),
            series_names,
        )
        + _plot_block(
            "Agent decision latency",
            "Decision-layer latency before generation or tool execution.",
            _summary_latency_chart(agent, "Hybrid agent decision latency"),
            series_names,
        )
        + _plot_block(
            "Agent decision API cost",
            "Estimated list-price cost for 1,000 decision-layer requests.",
            _summary_cost_chart(agent, "Hybrid agent decision cost"),
            series_names,
        )
    )

    pricing_rows = []
    for model, price in pricing["prices_per_million_tokens"].items():
        pricing_rows.append(
            "<tr>"
            f"<td>{model}</td><td>{price['input']}</td><td>{price.get('cached_input', '—')}</td>"
            f"<td>{price['output']}</td><td>{price['source']}</td>"
            "</tr>"
        )

    details_html = f"""
    <section class='table-card'>
      <div class='plot-copy'>
        <h3>Run metadata</h3>
        <p>These values define the measurement context used by every chart above.</p>
      </div>
      <dl class='details-grid'>
        <div><dt>Run group</dt><dd><code>{group_text}</code></dd></div>
        <div><dt>Suite</dt><dd>{suite}</dd></div>
        <div><dt>Runner</dt><dd>{locations}</dd></div>
        <div><dt>Pricing snapshot</dt><dd>{pricing['as_of']} · {pricing['processing']} · {pricing['currency']}</dd></div>
      </dl>
    </section>
    <section class='table-card'>
      <div class='plot-copy'>
        <h3>Pricing used</h3>
        <p>USD per 1M text tokens. Cost is an estimate from provider-reported token usage and this dated snapshot.</p>
      </div>
      <table><thead><tr><th>Model</th><th>Input</th><th>Cached input</th><th>Output</th><th>Source note</th></tr></thead>
      <tbody>{''.join(pricing_rows)}</tbody></table>
    </section>
    <section class='table-card'>
      <div class='plot-copy'><h3>Aggregate results</h3><p>Raw aggregate values for audit and deeper analysis.</p></div>
      {summary_table}
    </section>
    """

    tabs = [
        ("overview", "Overview", overview_html),
        ("routing", "Routing", routing_html),
        ("calibration", "Calibration", calibration_html),
        ("scaling", "Scaling", scaling_html),
        ("workflow", "Workflow", workflow_html),
        ("agent", "Agent", agent_html),
        ("details", "Run details", details_html),
    ]
    tab_buttons = "".join(
        f"<button class='tab-button {'active' if i == 0 else ''}' data-tab='{key}'>{label}</button>"
        for i, (key, label, _) in enumerate(tabs)
    )
    tab_sections = "".join(
        f"<section id='tab-{key}' class='tab-panel {'active' if i == 0 else ''}'>{body}</section>"
        for i, (key, _, body) in enumerate(tabs)
    )

    html = f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Jev vs GPT benchmark explorer</title>
<script src='https://cdn.plot.ly/plotly-3.1.0.min.js'></script>
<style>
:root{{--bg:#f5f6f8;--surface:#fff;--surface-2:#fafafa;--text:#111827;--muted:#667085;--line:#e4e7ec;--accent:#101828;--soft:#f2f4f7}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.shell{{max-width:1360px;margin:0 auto;padding:28px 24px 72px}}
.topbar{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:24px}}
.brand-kicker{{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}
h1{{font-size:38px;letter-spacing:-.03em;margin:5px 0 8px}} .lead{{max-width:800px;color:var(--muted);line-height:1.55;margin:0}}
.run-meta{{font-size:12px;color:var(--muted);text-align:right;line-height:1.7}} code{{background:var(--soft);padding:3px 6px;border-radius:6px}}
.toolbar{{position:sticky;top:0;z-index:20;background:rgba(245,246,248,.94);backdrop-filter:blur(12px);padding:10px 0 14px;border-bottom:1px solid var(--line)}}
.toolbar-row{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.tabs{{display:flex;gap:4px;overflow:auto}} .tab-button{{border:0;background:transparent;padding:9px 12px;border-radius:9px;color:var(--muted);font-weight:650;cursor:pointer;white-space:nowrap}}
.tab-button.active{{background:var(--accent);color:white}} .model-filter{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.filter-label{{font-size:12px;color:var(--muted);margin-right:4px}} .model-chip{{border:1px solid var(--line);background:white;border-radius:999px;padding:7px 10px;font-size:12px;cursor:pointer;color:var(--muted)}}
.model-chip.active{{color:var(--text);border-color:#98a2b3;box-shadow:0 1px 2px rgba(16,24,40,.05)}}
.notice{{margin:18px 0;background:#fffaeb;border:1px solid #fedf89;border-radius:12px;padding:12px 14px;font-size:13px;color:#7a2e0e}}
.tab-panel{{display:none;padding-top:18px}} .tab-panel.active{{display:block}}
.model-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:14px}}
.model-card,.plot-card,.table-card{{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 1px 2px rgba(16,24,40,.03)}}
.model-card{{padding:17px}} .model-name{{font-size:13px;font-weight:700;margin-bottom:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.metric-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}} .metric-row span{{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}} .metric-row strong{{font-size:18px;letter-spacing:-.02em}}
.card-foot{{border-top:1px solid var(--line);margin-top:14px;padding-top:10px;font-size:11px;color:var(--muted)}}
.plot-card,.table-card{{margin-bottom:14px;padding:16px}} .plot-copy{{padding:0 4px 8px}} .plot-copy h3{{margin:0 0 4px;font-size:17px}} .plot-copy p{{margin:0;color:var(--muted);font-size:13px;line-height:1.45;max-width:900px}}
.js-plotly-plot{{width:100%}} table{{width:100%;border-collapse:collapse;font-size:12px}} th,td{{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}} th{{color:var(--muted);font-weight:650;background:var(--surface-2)}}
.details-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:8px 0 0}} .details-grid div{{background:var(--surface-2);border-radius:10px;padding:12px}} dt{{font-size:11px;color:var(--muted);margin-bottom:4px}} dd{{margin:0;font-size:13px;font-weight:600}}
.empty{{color:var(--muted)}} @media(max-width:720px){{.shell{{padding:18px 12px 50px}}.topbar{{display:block}}.run-meta{{text-align:left;margin-top:12px}}h1{{font-size:30px}}.toolbar{{top:0}}.toolbar-row{{align-items:flex-start}}}}
</style>
</head>
<body>
<div class='shell'>
  <header class='topbar'>
    <div>
      <div class='brand-kicker'>Decision benchmark explorer</div>
      <h1>Jev vs GPT</h1>
      <p class='lead'>Compare decision quality, latency, calibration and estimated API cost across Jev, the configured GPT matrix and optional Korgis local models. Use the model chips to focus every chart on the systems you want to inspect.</p>
    </div>
    <div class='run-meta'>Run <code>{group_text}</code><br>{suite}<br>{locations}<br>Pricing {pricing['as_of']}</div>
  </header>

  <div class='toolbar'>
    <div class='toolbar-row'>
      <nav class='tabs'>{tab_buttons}</nav>
      <div class='model-filter'><span class='filter-label'>Models</span>{model_chips}</div>
    </div>
  </div>

  <div class='notice'><strong>Publication note:</strong> verify the TypeSafe terms applicable to the account before publishing Jev performance numbers. Cloud API cost values are estimates using the dated list-price snapshot shown in Run details. Korgis local models have zero provider API fee; electricity, hardware purchase/amortisation and device opportunity cost are not measured and are not claimed to be zero.</div>
  {tab_sections}
</div>
<script>
const tabs = document.querySelectorAll('.tab-button');
const panels = document.querySelectorAll('.tab-panel');
tabs.forEach(btn => btn.addEventListener('click', () => {{
  tabs.forEach(x => x.classList.remove('active'));
  panels.forEach(x => x.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  window.dispatchEvent(new Event('resize'));
}}));

const chips = [...document.querySelectorAll('.model-chip')];
function activeSeries() {{
  return new Set(chips.filter(x => x.classList.contains('active')).map(x => x.dataset.series));
}}
function applyModelFilter() {{
  const active = activeSeries();
  document.querySelectorAll('.plotly-graph-div').forEach(div => {{
    if (!div.data) return;
    const visible = div.data.map(trace => {{
      const series = trace.meta && trace.meta.series;
      if (!series) return true;
      return active.has(series) ? true : 'legendonly';
    }});
    Plotly.restyle(div, {{visible}});
  }});
  document.querySelectorAll('.model-card').forEach(card => {{
    card.style.display = active.has(card.dataset.series) ? '' : 'none';
  }});
}}
chips.forEach(chip => chip.addEventListener('click', () => {{
  chip.classList.toggle('active');
  applyModelFilter();
}}));
</script>
</body>
</html>"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
