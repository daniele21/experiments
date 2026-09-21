from __future__ import annotations

import html
import json
from pathlib import Path


def write_document_html(
    path: Path,
    extraction: dict,
    model_summaries: dict[str, dict],
    manifest: dict,
) -> None:
    rows = []
    for model, summary in model_summaries.items():
        quality = summary["model_on_extracted_text"]
        e2e = summary["end_to_end"]
        rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td>"
            f"<td>{quality.get('pii_recall', 0):.4f}</td>"
            f"<td>{e2e.get('e2e_pii_recall', 0):.4f}</td>"
            f"<td>{e2e.get('e2e_leakage_rate', 0):.4f}</td>"
            f"<td>{e2e.get('e2e_zero_leak_document_rate', 0):.4f}</td>"
            f"<td>{quality.get('precision', 0):.4f}</td>"
            f"<td>{quality.get('latency_p50_ms', 0) or 0:.1f}</td>"
            "</tr>"
        )

    payload = html.escape(json.dumps(manifest, indent=2, ensure_ascii=False))
    extraction_payload = html.escape(json.dumps(extraction, indent=2, ensure_ascii=False))
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>RedactGuard document E2E benchmark</title>
<style>
body{{font-family:system-ui,sans-serif;margin:40px;max-width:1400px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:right}}
th:first-child,td:first-child{{text-align:left}}
pre{{background:#f5f5f5;padding:16px;overflow:auto}}
</style></head><body>
<h1>RedactGuard document E2E benchmark</h1>
<p>The report separates PDF extraction quality from model quality. End-to-end recall counts PII lost by Docling as misses.</p>
<h2>Extraction</h2>
<pre>{extraction_payload}</pre>
<h2>Models</h2>
<table><thead><tr>
<th>Model</th><th>Model recall on extracted text</th><th>E2E recall</th>
<th>E2E leakage</th><th>Zero-leak documents</th><th>Precision</th><th>p50 ms/page</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Manifest</h2><pre>{payload}</pre>
</body></html>"""
    path.write_text(document, encoding="utf-8")
