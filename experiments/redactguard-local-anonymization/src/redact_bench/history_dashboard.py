from __future__ import annotations

import html
from pathlib import Path

from redact_bench.history import load_history


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _latest_table(entry: dict) -> str:
    rows = []
    for model, payload in entry.get("models", {}).items():
        quality = payload["quality"]
        latency = payload["latency"]
        rows.append(
            "<tr>"
            f"<td>{_esc(model)}</td>"
            f"<td>{_pct(quality.get('micro_recall'))}</td>"
            f"<td>{_pct(quality.get('macro_recall'))}</td>"
            f"<td>{_pct(quality.get('micro_leakage'))}</td>"
            f"<td>{_pct(quality.get('macro_leakage'))}</td>"
            f"<td>{_pct(quality.get('micro_precision'))}</td>"
            f"<td>{_pct(quality.get('zero_leak_documents'))}</td>"
            f"<td>{_ms(latency.get('p50_ms'))}</td>"
            f"<td>{_ms(latency.get('p95_ms'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Model</th><th>Micro recall</th>"
        "<th>Macro recall</th><th>Micro leakage</th><th>Macro leakage</th>"
        "<th>Precision</th><th>Zero-leak docs</th><th>Latency p50 ms</th>"
        "<th>Latency p95 ms</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _history_table(entries: list[dict]) -> str:
    rows = []
    for entry in reversed(entries):
        suite_id = entry["suite_id"]
        quality_link = f"suites/{suite_id}/quality/report.html"
        latency_link = f"suites/{suite_id}/latency/report.html"
        for model, payload in entry.get("models", {}).items():
            quality = payload["quality"]
            latency = payload["latency"]
            rows.append(
                "<tr>"
                f"<td>{_esc(entry.get('created_at'))}</td>"
                f"<td>{_esc(suite_id)}</td>"
                f"<td>{_esc(model)}</td>"
                f"<td>{_pct(quality.get('micro_recall'))}</td>"
                f"<td>{_pct(quality.get('macro_recall'))}</td>"
                f"<td>{_pct(quality.get('micro_leakage'))}</td>"
                f"<td>{_pct(quality.get('macro_leakage'))}</td>"
                f"<td>{_pct(quality.get('micro_precision'))}</td>"
                f"<td>{_ms(latency.get('p50_ms'))}</td>"
                f"<td>{_ms(latency.get('p95_ms'))}</td>"
                f"<td><a href='{_esc(quality_link)}'>quality</a> · "
                f"<a href='{_esc(latency_link)}'>latency</a></td>"
                "</tr>"
            )
    return (
        "<div class='scroll'><table><thead><tr><th>Run</th><th>Suite</th>"
        "<th>Model</th><th>Micro recall</th><th>Macro recall</th>"
        "<th>Micro leakage</th><th>Macro leakage</th><th>Precision</th>"
        "<th>p50 ms</th><th>p95 ms</th><th>Details</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _type_table(entry: dict) -> str:
    rows = []
    for model, payload in entry.get("models", {}).items():
        for pii_type, metrics in payload["quality"].get("by_type", {}).items():
            rows.append(
                "<tr>"
                f"<td>{_esc(model)}</td><td>{_esc(pii_type)}</td>"
                f"<td>{_pct(metrics.get('pii_recall'))}</td>"
                f"<td>{_pct(metrics.get('precision'))}</td>"
                f"<td>{_pct(metrics.get('leakage_rate'))}</td>"
                f"<td>{metrics.get('gold_count', '—')}</td>"
                "</tr>"
            )
    return (
        "<table><thead><tr><th>Model</th><th>PII type</th><th>Recall</th>"
        "<th>Precision</th><th>Leakage</th><th>Gold spans</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def write_history_dashboard(
    history_path: str | Path,
    output_path: str | Path,
) -> Path:
    entries = load_history(history_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not entries:
        destination.write_text(
            "<!doctype html><html><body><h1>RedactGuard benchmark history</h1>"
            "<p>No completed suites yet.</p></body></html>",
            encoding="utf-8",
        )
        return destination

    latest = entries[-1]
    suite_id = latest.get("suite_id")
    korgis = latest.get("korgis") or {}
    document = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>RedactGuard benchmark history</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif}}
body{{margin:36px;max-width:1700px;line-height:1.45;background:#fafafa;color:#171717}}
h1,h2{{line-height:1.15}}
.panel{{background:white;border:1px solid #ddd;border-radius:12px;padding:20px;margin:18px 0}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}
.card{{background:white;border:1px solid #ddd;border-radius:10px;padding:12px 16px;min-width:180px}}
.card strong{{display:block;font-size:12px;opacity:.65}}
.card span{{font-size:18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:white}}
th,td{{border-bottom:1px solid #e6e6e6;padding:9px;text-align:right;white-space:nowrap}}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3){{text-align:left}}
th{{position:sticky;top:0;background:#f4f4f4}}
.scroll{{overflow:auto;max-height:720px}}
a{{color:inherit}}
.note{{border-left:4px solid #777;padding:10px 14px;background:#f0f0f0}}
</style>
</head>
<body>
<h1>RedactGuard benchmark history</h1>
<p class="note">Each suite manages Korgis, runs every model in a fresh runtime process,
executes quality and repeated latency, appends one immutable history entry, and rebuilds this dashboard.</p>
<div class="cards">
<div class="card"><strong>Latest suite</strong><span>{_esc(suite_id)}</span></div>
<div class="card"><strong>Dataset</strong><span>{_esc(latest.get('dataset_id'))}</span></div>
<div class="card"><strong>Completed suites</strong><span>{len(entries)}</span></div>
<div class="card"><strong>Models in latest suite</strong><span>{len(latest.get('models', {}))}</span></div>
<div class="card"><strong>Runtime strategy</strong><span>{_esc(latest.get('runtime_strategy'))}</span></div>
<div class="card"><strong>Korgis SHA</strong><span>{_esc(korgis.get('source_sha'))}</span></div>
</div>
<p>
<a href="suites/{_esc(suite_id)}/quality/report.html">Open latest quality report</a>
&nbsp;·&nbsp;
<a href="suites/{_esc(suite_id)}/latency/report.html">Open latest latency report</a>
</p>

<section class="panel"><h2>Latest model comparison</h2>{_latest_table(latest)}</section>
<section class="panel"><h2>Latest performance by PII type</h2>{_type_table(latest)}</section>
<section class="panel"><h2>Run history</h2>{_history_table(entries)}</section>
</body>
</html>"""
    destination.write_text(document, encoding="utf-8")
    return destination
