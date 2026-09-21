from __future__ import annotations

import html
import json
from pathlib import Path


def write_html(path: Path, summaries: dict[str, dict], manifest: dict) -> None:
    columns = [
        ("pii_recall", "PII recall"),
        ("leakage_rate", "Leakage"),
        ("zero_leak_document_rate", "Zero-leak docs"),
        ("precision", "Precision"),
        ("over_redaction_rate", "Over-redaction"),
        ("valid_output_rate", "Valid output"),
        ("latency_p50_ms", "p50 ms"),
        ("latency_p95_ms", "p95 ms"),
    ]
    headers = "".join(f"<th>{label}</th>" for _, label in columns)
    body = []
    for model, summary in summaries.items():
        cells = []
        for key, _ in columns:
            value = summary.get(key)
            if isinstance(value, float):
                cells.append(f"<td>{value:.4f}</td>")
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append(f"<tr><td>{html.escape(model)}</td>{''.join(cells)}</tr>")
    payload = html.escape(json.dumps(manifest, indent=2, ensure_ascii=False))
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>RedactGuard local anonymization benchmark</title>
<style>
body{{font-family:system-ui,sans-serif;margin:40px;max-width:1400px}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:right}} th:first-child,td:first-child{{text-align:left}}
pre{{background:#f5f5f5;padding:16px;overflow:auto}}
</style></head><body>
<h1>RedactGuard local anonymization benchmark</h1>
<p>Primary privacy metrics are recall, leakage and zero-leak document rate. Lower leakage and over-redaction are better.</p>
<table><thead><tr><th>Model</th>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table>
<h2>Run manifest</h2><pre>{payload}</pre>
</body></html>"""
    path.write_text(document, encoding="utf-8")
