from __future__ import annotations

import html as html_lib
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



def _safe(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return html_lib.escape(str(value))


def _fmt_number(value: object, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def _experiment_rows(rows: pd.DataFrame, prefix: str) -> pd.DataFrame:
    public_name = f"{prefix}-public"
    if rows["experiment"].eq(public_name).any():
        return rows[rows["experiment"].eq(public_name)].copy()
    return rows[rows["experiment"].eq(prefix)].copy()


def _per_class_table(rows: pd.DataFrame) -> str:
    subset = rows[
        rows["primary_metric"].fillna(False)
        & rows["expected"].notna()
    ].copy()
    if subset.empty:
        return "<p class='empty'>No class-level data in this run.</p>"
    subset = _with_series(subset)
    records: list[dict[str, object]] = []
    for (series, expected), frame in subset.groupby(["series", "expected"], dropna=False):
        valid = frame[frame["valid"]]
        wrong = valid[~valid["correct"] & valid["actual"].notna()]
        top_wrong = (
            wrong["actual"].astype(str).value_counts().index[0]
            if not wrong.empty
            else "—"
        )
        records.append(
            {
                "model": series,
                "class": expected,
                "cases": frame["case_id"].nunique(),
                "valid_rate": float(frame.groupby("case_id")["valid"].all().mean()),
                "accuracy": float(valid["correct"].mean()) if len(valid) else math.nan,
                "top_wrong_prediction": top_wrong,
            }
        )
    table = pd.DataFrame(records).sort_values(["model", "accuracy", "class"])
    return table.to_html(
        index=False,
        classes="data-table granular-table",
        float_format=lambda value: f"{value:.3f}",
    )


def _cost_breakdown(rows: pd.DataFrame):
    if "estimated_cost_usd" not in rows.columns:
        return _empty_chart("API cost by experiment — unavailable")
    valid = _with_series(rows[rows["valid"]].copy())
    if valid.empty:
        return _empty_chart("API cost by experiment — no valid requests")
    requests = valid.sort_values("case_id").drop_duplicates(
        ["experiment", "case_id", "provider", "model"]
    )
    data = (
        requests.groupby(["experiment", "series"], as_index=False)
        .agg(
            requests=("case_id", "nunique"),
            total_api_cost_usd=("estimated_cost_usd", "sum"),
            mean_api_cost_usd=("estimated_cost_usd", "mean"),
        )
    )
    data["cost_per_1k_requests_usd"] = data["mean_api_cost_usd"] * 1000
    return px.bar(
        data,
        x="experiment",
        y="cost_per_1k_requests_usd",
        color="series",
        barmode="group",
        title="API cost by experiment",
        labels={
            "experiment": "experiment",
            "cost_per_1k_requests_usd": "API USD / 1,000 requests",
            "series": "model",
        },
        hover_data=["requests", "total_api_cost_usd", "mean_api_cost_usd"],
    )


def _case_status(frame: pd.DataFrame) -> tuple[str, str]:
    valid = bool(frame["valid"].all())
    primary = frame[frame["primary_metric"].fillna(False)]
    if not valid:
        return "Invalid", "bad"
    if len(primary):
        if bool(primary["correct"].all()):
            return "Correct", "good"
        return "Wrong", "bad"
    return "Valid", "neutral"


def _case_explorer(rows: pd.DataFrame, experiment: str, title: str) -> str:
    subset = _experiment_rows(rows, experiment)
    if subset.empty:
        return (
            "<section class='table-card'><div class='plot-copy'>"
            f"<h3>{_safe(title)}</h3><p class='empty'>No case-level data in this run.</p>"
            "</div></section>"
        )

    subset = _with_series(subset)
    cards: list[str] = []
    grouped = subset.groupby(["series", "case_id"], sort=True, dropna=False)
    for (series, case_id), frame in grouped:
        frame = frame.copy()
        status, status_class = _case_status(frame)
        first = frame.iloc[0]
        input_state = first.get("input_state", "")
        if pd.isna(input_state):
            input_state = ""
        primary = frame[frame["primary_metric"].fillna(False)]
        latency = float(frame["latency_ms"].dropna().iloc[0]) if frame["latency_ms"].notna().any() else math.nan
        request_cost = (
            float(frame["estimated_cost_usd"].dropna().iloc[0])
            if "estimated_cost_usd" in frame and frame["estimated_cost_usd"].notna().any()
            else math.nan
        )

        decision_rows: list[str] = []
        for _, row in frame.sort_values(
            ["primary_metric", "question_id"],
            ascending=[True, True],
        ).iterrows():
            expected = row.get("expected")
            actual = row.get("actual")
            icon = "✓" if bool(row.get("correct")) else "✕"
            valid_icon = "✓" if bool(row.get("valid")) else "✕"
            decision_rows.append(
                "<tr>"
                f"<td><code>{_safe(row.get('question_id'))}</code></td>"
                f"<td>{_safe(expected)}</td>"
                f"<td>{_safe(actual)}</td>"
                f"<td>{icon}</td>"
                f"<td>{_fmt_number(row.get('confidence'))}</td>"
                f"<td>{_fmt_number(row.get('predicted_probability'))}</td>"
                f"<td>{valid_icon}</td>"
                f"<td>{_safe(row.get('error'))}</td>"
                "</tr>"
            )

        trace_html = ""
        if "decision_trace" in frame.columns:
            traces = frame["decision_trace"].dropna().astype(str)
            if len(traces):
                trace_text = traces.iloc[-1]
                try:
                    trace_obj = json.loads(trace_text)
                    trace_text = json.dumps(
                        trace_obj,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                except json.JSONDecodeError:
                    pass
                trace_html = (
                    "<div class='trace-block'><h4>Decision trace</h4>"
                    f"<pre>{_safe(trace_text)}</pre></div>"
                )

        primary_text = ""
        if len(primary):
            p = primary.iloc[-1]
            primary_text = (
                f"<span>Final: <strong>{_safe(p.get('actual'))}</strong>"
                f" / expected {_safe(p.get('expected'))}</span>"
            )

        search_blob = " ".join(
            [
                str(series),
                str(case_id),
                str(input_state),
                " ".join(frame["expected"].dropna().astype(str)),
                " ".join(frame["actual"].dropna().astype(str)),
                " ".join(frame["error"].dropna().astype(str))
                if "error" in frame
                else "",
            ]
        ).lower()

        cards.append(
            f"<details class='case-card' data-series={json.dumps(str(series))} "
            f"data-search={json.dumps(search_blob)}>"
            "<summary>"
            f"<span class='status-dot {status_class}'></span>"
            f"<strong>{_safe(case_id)}</strong>"
            f"<span class='case-model'>{_safe(series)}</span>"
            f"<span class='status-pill {status_class}'>{status}</span>"
            f"<span>{_fmt_number(latency, 0)} ms</span>"
            f"<span>{_money(request_cost)}</span>"
            f"{primary_text}"
            "</summary>"
            f"<div class='case-input'><span>Input</span><p>{_safe(input_state)}</p></div>"
            "<div class='request-meta'>"
            f"<span>Latency <strong>{_fmt_number(latency, 0)} ms</strong></span>"
            f"<span>Input tokens <strong>{_safe(first.get('input_tokens'))}</strong></span>"
            f"<span>Output tokens <strong>{_safe(first.get('output_tokens'))}</strong></span>"
            f"<span>API cost <strong>{_money(request_cost)}</strong></span>"
            f"<span>Difficulty <strong>{_safe(first.get('difficulty'))}</strong></span>"
            "</div>"
            "<div class='table-scroll'><table class='decision-table'>"
            "<thead><tr><th>Decision</th><th>Expected</th><th>Actual</th>"
            "<th>Correct</th><th>Confidence</th><th>Probability</th>"
            "<th>Valid</th><th>Error</th></tr></thead>"
            f"<tbody>{''.join(decision_rows)}</tbody></table></div>"
            f"{trace_html}"
            "</details>"
        )

    return (
        "<section class='table-card explorer-card'>"
        f"<div class='plot-copy'><h3>{_safe(title)}</h3>"
        "<p>Search by case id, input, expected/actual output or error. Expand a case to inspect every decision.</p></div>"
        "<div class='explorer-tools'>"
        "<input class='case-search' type='search' placeholder='Search cases, inputs, outputs, errors…' "
        "aria-label='Search cases'>"
        f"<span class='case-count'>{len(cards)} cases</span>"
        "</div>"
        f"<div class='case-list'>{''.join(cards)}</div>"
        "</section>"
    )


def _error_explorer(rows: pd.DataFrame, experiment: str) -> str:
    subset = _experiment_rows(rows, experiment)
    if subset.empty:
        return ""
    subset = _with_series(subset)
    errors = subset[(~subset["valid"]) | subset["error"].notna()].copy()
    if errors.empty:
        return (
            "<section class='table-card'><div class='plot-copy'>"
            "<h3>Error explorer</h3><p>No schema/provider errors in this experiment.</p>"
            "</div></section>"
        )
    columns = [
        "series",
        "case_id",
        "question_id",
        "error",
        "latency_ms",
        "input_tokens",
        "output_tokens",
    ]
    available = [column for column in columns if column in errors.columns]
    return (
        "<section class='table-card'><div class='plot-copy'>"
        "<h3>Error explorer</h3>"
        "<p>Provider, schema and missing-answer failures are kept separate from semantic mistakes.</p>"
        "</div><div class='table-scroll'>"
        + errors[available].drop_duplicates().to_html(
            index=False,
            classes="data-table granular-table",
            float_format=lambda value: f"{value:.3f}",
        )
        + "</div></section>"
    )


def _scaling_detail_table(rows: pd.DataFrame) -> str:
    subset = rows[rows["experiment"].eq("03-parallel-scaling")].copy()
    if subset.empty:
        return "<p class='empty'>No scaling requests in this run.</p>"
    subset = _with_series(subset)
    columns = [
        "series",
        "case_id",
        "question_count",
        "valid",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "error",
    ]
    return subset[[column for column in columns if column in subset.columns]].to_html(
        index=False,
        classes="data-table granular-table",
        float_format=lambda value: f"{value:.4f}",
    )


def build_report(raw_csv: Path, output_html: Path, run_group: str | None = None) -> None:
    all_rows = pd.read_csv(raw_csv)
    rows, selected_group = _select_run_group(all_rows, run_group)
    summary = _with_series(summarize(rows))
    overview = _overview(rows)
    experiment_cost = _cost_breakdown(rows)

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
        + _plot_block(
            "API cost by experiment",
            "Breaks estimated provider API cost down by workload instead of hiding it behind one run-level average.",
            experiment_cost,
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
        + "<section class='table-card'><div class='plot-copy'><h3>Per-class breakdown</h3>"
          "<p>Accuracy and valid-output rate for every expected routing class, including the most frequent wrong prediction.</p>"
          "</div><div class='table-scroll'>"
        + _per_class_table(_experiment_rows(rows, "01-routing"))
        + "</div></section>"
        + _case_explorer(rows, "01-routing", "Routing cases")
        + _error_explorer(rows, "01-routing")
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
        + _case_explorer(rows, "02-calibration", "Calibration predictions")
        + _error_explorer(rows, "02-calibration")
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
        + "<section class='table-card'><div class='plot-copy'><h3>Every scaling request</h3>"
          "<p>Inspect validity, latency, token usage, estimated cost and the exact error for each 1/2/4/8/16/32-question request.</p>"
          "</div><div class='table-scroll'>"
        + _scaling_detail_table(rows)
        + "</div></section>"
        + _error_explorer(rows, "03-parallel-scaling")
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
        + _case_explorer(rows, "04-workflow", "Workflow execution traces")
        + _error_explorer(rows, "04-workflow")
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
        + _case_explorer(rows, "05-hybrid-agent", "Agent execution traces")
        + _error_explorer(rows, "05-hybrid-agent")
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
<title>Decision model benchmark explorer</title>
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
.table-scroll{{overflow:auto;max-width:100%}} .data-table{{min-width:760px}}
.explorer-tools{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:4px 4px 12px}} .case-search{{width:min(560px,100%);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit;background:white}} .case-count{{font-size:12px;color:var(--muted);white-space:nowrap}}
.case-list{{display:grid;gap:8px}} .case-card{{border:1px solid var(--line);border-radius:12px;background:var(--surface-2);overflow:hidden}} .case-card summary{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 14px;cursor:pointer;list-style:none;font-size:12px}} .case-card summary::-webkit-details-marker{{display:none}} .case-model{{color:var(--muted);margin-right:auto}} .case-card[open] summary{{border-bottom:1px solid var(--line);background:white}}
.status-dot{{width:8px;height:8px;border-radius:50%;background:#98a2b3}} .status-dot.good{{background:#17b26a}} .status-dot.bad{{background:#f04438}} .status-pill{{padding:3px 7px;border-radius:999px;font-size:11px;font-weight:700;background:#f2f4f7}} .status-pill.good{{background:#ecfdf3;color:#067647}} .status-pill.bad{{background:#fef3f2;color:#b42318}}
.case-input{{padding:14px}} .case-input span,.trace-block h4{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}} .case-input p{{margin:5px 0 0;white-space:pre-wrap;line-height:1.5}} .request-meta{{display:flex;gap:8px;flex-wrap:wrap;padding:0 14px 14px}} .request-meta span{{background:white;border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:11px;color:var(--muted)}} .request-meta strong{{color:var(--text)}} .decision-table{{min-width:900px;background:white}} .trace-block{{margin:12px 14px 14px}} .trace-block pre{{white-space:pre-wrap;word-break:break-word;background:#101828;color:#f9fafb;border-radius:10px;padding:12px;font-size:11px;overflow:auto}}
.empty{{color:var(--muted)}} @media(max-width:720px){{.shell{{padding:18px 12px 50px}}.topbar{{display:block}}.run-meta{{text-align:left;margin-top:12px}}h1{{font-size:30px}}.toolbar{{top:0}}.toolbar-row{{align-items:flex-start}}}}
</style>
</head>
<body>
<div class='shell'>
  <header class='topbar'>
    <div>
      <div class='brand-kicker'>Decision benchmark explorer</div>
      <h1>Decision model benchmark</h1>
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
  document.querySelectorAll('.model-card,.case-card').forEach(card => {{
    card.style.display = active.has(card.dataset.series) ? '' : 'none';
  }});
  document.querySelectorAll('table.granular-table tbody tr').forEach(row => {{
    const series = row.cells.length ? row.cells[0].textContent.trim() : '';
    row.style.display = series && active.has(series) ? '' : 'none';
  }});
  document.querySelectorAll('.case-search').forEach(input => input.dispatchEvent(new Event('input')));
}}
chips.forEach(chip => chip.addEventListener('click', () => {{
  chip.classList.toggle('active');
  applyModelFilter();
}}));

document.querySelectorAll('.case-search').forEach(input => {{
  input.addEventListener('input', () => {{
    const query = input.value.trim().toLowerCase();
    const active = activeSeries();
    const card = input.closest('.explorer-card');
    if (!card) return;
    let visible = 0;
    card.querySelectorAll('.case-card').forEach(item => {{
      const seriesVisible = active.has(item.dataset.series);
      const textVisible = !query || (item.dataset.search || '').includes(query);
      item.style.display = seriesVisible && textVisible ? '' : 'none';
      if (seriesVisible && textVisible) visible += 1;
    }});
    const count = card.querySelector('.case-count');
    if (count) count.textContent = visible + ' cases';
  }});
}}));
</script>
</body>
</html>"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
