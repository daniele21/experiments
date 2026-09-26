from __future__ import annotations

import html
import json
from pathlib import Path


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def _ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def _num(value: int | float | None) -> str:
    return "—" if value is None else str(value)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _span_list(spans: list[dict], *, limit: int = 12) -> str:
    if not spans:
        return "<span class='muted'>none</span>"
    items = []
    for span in spans[:limit]:
        items.append(
            "<li><code>"
            + _esc(span.get("pii_type"))
            + "</code> "
            + _esc(span.get("value"))
            + "</li>"
        )
    if len(spans) > limit:
        items.append(f"<li class='muted'>… {len(spans) - limit} more</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _overview_table(summaries: dict[str, dict]) -> str:
    rows = []
    for model, summary in summaries.items():
        micro = summary.get("micro", summary)
        macro = summary.get("macro", {})
        rows.append(
            "<tr>"
            f"<td>{_esc(model)}</td>"
            f"<td>{_pct(micro.get('pii_recall'))}</td>"
            f"<td>{_pct(macro.get('pii_recall'))}</td>"
            f"<td>{_pct(micro.get('leakage_rate'))}</td>"
            f"<td>{_pct(macro.get('leakage_rate'))}</td>"
            f"<td>{_pct(micro.get('precision'))}</td>"
            f"<td>{_pct(macro.get('precision'))}</td>"
            f"<td>{_pct(micro.get('zero_leak_document_rate'))}</td>"
            f"<td>{_pct(micro.get('valid_output_rate'))}</td>"
            f"<td>{_ms(micro.get('latency_p50_ms'))}</td>"
            f"<td>{_ms(micro.get('latency_p95_ms'))}</td>"
            "</tr>"
        )
    return """<table>
<thead><tr>
<th>Model</th><th>Micro recall</th><th>Macro recall</th>
<th>Micro leakage</th><th>Macro leakage</th>
<th>Micro precision</th><th>Macro precision</th>
<th>Zero-leak docs</th><th>Valid output</th><th>p50 ms</th><th>p95 ms</th>
</tr></thead>
<tbody>""" + "".join(rows) + "</tbody></table>"


def _dataset_balance(summaries: dict[str, dict]) -> str:
    if not summaries:
        return ""
    first = next(iter(summaries.values()))
    balance = first.get("dataset_balance", {})
    if not balance:
        return ""

    type_rows = "".join(
        f"<tr><td>{_esc(pii_type)}</td><td>{count}</td></tr>"
        for pii_type, count in balance.get("gold_spans_by_type", {}).items()
    )
    document_rows = "".join(
        f"<tr><td>{_esc(case_id)}</td><td>{count}</td>"
        f"<td>{_pct(count / balance['gold_spans'] if balance.get('gold_spans') else 0.0)}</td></tr>"
        for case_id, count in sorted(
            balance.get("gold_spans_by_document", {}).items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )
    return f"""
<div class="cards">
  <div class="card"><strong>Documents</strong><span>{_num(balance.get('documents'))}</span></div>
  <div class="card"><strong>Gold spans</strong><span>{_num(balance.get('gold_spans'))}</span></div>
  <div class="card"><strong>Largest document</strong><span>{_esc(balance.get('largest_document'))}</span></div>
  <div class="card"><strong>Largest share</strong><span>{_pct(balance.get('largest_document_share'))}</span></div>
</div>
<div class="grid">
<section><h3>Gold by PII type</h3><table><thead><tr><th>PII type</th><th>Gold spans</th></tr></thead>
<tbody>{type_rows}</tbody></table></section>
<section><h3>Gold by document</h3><table><thead><tr><th>Document</th><th>Gold spans</th><th>Share</th></tr></thead>
<tbody>{document_rows}</tbody></table></section>
</div>
"""


def _type_breakdown(summaries: dict[str, dict]) -> str:
    rows = []
    for model, summary in summaries.items():
        for pii_type, metrics in summary.get("by_type", {}).items():
            rows.append(
                "<tr>"
                f"<td>{_esc(model)}</td>"
                f"<td>{_esc(pii_type)}</td>"
                f"<td>{_num(metrics.get('gold_count'))}</td>"
                f"<td>{_num(metrics.get('predicted_count'))}</td>"
                f"<td>{_pct(metrics.get('pii_recall'))}</td>"
                f"<td>{_pct(metrics.get('precision'))}</td>"
                f"<td>{_pct(metrics.get('span_f1'))}</td>"
                f"<td>{_pct(metrics.get('leakage_rate'))}</td>"
                f"<td>{_pct(metrics.get('exact_match_recall'))}</td>"
                "</tr>"
            )
    return """<table>
<thead><tr>
<th>Model</th><th>PII type</th><th>Gold</th><th>Predicted</th>
<th>Recall</th><th>Precision</th><th>F1</th><th>Type leakage</th><th>Exact recall</th>
</tr></thead><tbody>""" + "".join(rows) + "</tbody></table>"


def _document_breakdown(summaries: dict[str, dict]) -> str:
    rows = []
    for model, summary in summaries.items():
        documents = summary.get("by_document", {})
        ordered = sorted(
            documents.items(),
            key=lambda item: (
                item[1].get("leakage_rate", 0.0),
                item[1].get("fn", 0),
                item[1].get("fp", 0),
            ),
            reverse=True,
        )
        for case_id, metrics in ordered:
            rows.append(
                "<tr>"
                f"<td>{_esc(model)}</td>"
                f"<td>{_esc(case_id)}</td>"
                f"<td>{_esc(metrics.get('profile'))}</td>"
                f"<td>{_num(metrics.get('gold_count_per_document'))}</td>"
                f"<td>{_pct(metrics.get('pii_recall'))}</td>"
                f"<td>{_pct(metrics.get('leakage_rate'))}</td>"
                f"<td>{_pct(metrics.get('precision'))}</td>"
                f"<td>{_pct(metrics.get('over_redaction_rate'))}</td>"
                f"<td>{_pct(metrics.get('zero_leak_document_rate'))}</td>"
                f"<td>{_num(metrics.get('fn'))}</td>"
                f"<td>{_num(metrics.get('fp'))}</td>"
                f"<td>{_ms(metrics.get('latency_p50_ms'))}</td>"
                "</tr>"
            )
    return """<div class="scroll"><table>
<thead><tr>
<th>Model</th><th>Document</th><th>Profile</th><th>Gold</th>
<th>Recall</th><th>Leakage</th><th>Precision</th><th>Over-redaction</th>
<th>Zero leak</th><th>FN</th><th>FP</th><th>p50 ms</th>
</tr></thead><tbody>""" + "".join(rows) + "</tbody></table></div>"


def _failure_analysis(summaries: dict[str, dict]) -> str:
    blocks = []
    for model, summary in summaries.items():
        failures = summary.get("failure_analysis", [])
        if not failures:
            blocks.append(
                f"<section><h3>{_esc(model)}</h3>"
                "<p class='muted'>No quality or output failures recorded.</p></section>"
            )
            continue

        details = []
        for failure in failures[:12]:
            details.append(
                "<details>"
                "<summary>"
                f"{_esc(failure['case_id'])} · "
                f"recall {_pct(failure.get('pii_recall'))} · "
                f"leakage {_pct(failure.get('leakage_rate'))} · "
                f"FN {_num(failure.get('fn'))} · FP {_num(failure.get('fp'))}"
                "</summary>"
                "<div class='failure-grid'>"
                "<div><h4>Missed gold spans</h4>"
                + _span_list(failure.get("false_negatives", []))
                + "</div>"
                "<div><h4>Unmatched predictions</h4>"
                + _span_list(failure.get("false_positives", []))
                + "</div>"
                "</div>"
                + (
                    f"<p><strong>Error:</strong> {_esc(failure.get('error'))}</p>"
                    if failure.get("error")
                    else ""
                )
                + "</details>"
            )
        blocks.append(
            f"<section><h3>{_esc(model)}</h3>{''.join(details)}</section>"
        )
    return "".join(blocks)


def write_html(path: Path, summaries: dict[str, dict], manifest: dict) -> None:
    payload = html.escape(json.dumps(manifest, indent=2, ensure_ascii=False))
    document = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>RedactGuard local anonymization benchmark</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif}}
body{{margin:36px;max-width:1600px;line-height:1.45}}
h1,h2,h3{{line-height:1.2}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border:1px solid #ddd;padding:8px;text-align:right;vertical-align:top}}
th:first-child,td:first-child{{text-align:left}}
th:nth-child(2),td:nth-child(2){{text-align:left}}
pre{{background:#f5f5f5;padding:16px;overflow:auto}}
code{{font-size:.92em}}
.muted{{opacity:.7}}
.scroll{{overflow:auto}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.card{{border:1px solid #ddd;border-radius:8px;padding:12px 16px;min-width:160px}}
.card strong{{display:block;font-size:12px;opacity:.7}}
.card span{{display:block;font-size:20px;margin-top:3px}}
.grid{{display:grid;grid-template-columns:1fr 2fr;gap:24px;align-items:start}}
details{{border:1px solid #ddd;border-radius:8px;padding:10px 12px;margin:10px 0}}
summary{{cursor:pointer;font-weight:600}}
.failure-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
section{{margin:28px 0}}
.note{{border-left:4px solid #999;padding:8px 12px;background:#f7f7f7}}
@media(max-width:900px){{.grid,.failure-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>RedactGuard local anonymization benchmark</h1>
<p class="note">
Evaluation v2 reports both <strong>micro</strong> metrics (every gold span has equal weight)
and <strong>macro</strong> metrics (every document has equal weight). Do not infer overall
quality from micro recall alone when the dataset is imbalanced.
</p>

<h2>Model overview</h2>
{_overview_table(summaries)}

<h2>Dataset composition</h2>
{_dataset_balance(summaries)}

<h2>Performance by PII type</h2>
{_type_breakdown(summaries)}

<h2>Performance by document</h2>
{_document_breakdown(summaries)}

<h2>Failure analysis</h2>
<p>Cases are ordered by leakage, then false negatives and false positives.</p>
{_failure_analysis(summaries)}

<h2>Run manifest</h2>
<pre>{payload}</pre>
</body>
</html>"""
    path.write_text(document, encoding="utf-8")
