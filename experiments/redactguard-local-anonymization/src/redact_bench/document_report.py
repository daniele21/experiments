from __future__ import annotations

import html
import json
from pathlib import Path


def _metric(value: float | None, *, digits: int = 4) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


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
        status = (
            "quality N/A"
            if quality.get("quality_available") is False
            else "valid"
        )
        rows.append(
            "<tr>"
            f"<td>{html.escape(model)}</td>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{_metric(quality.get('pii_recall'))}</td>"
            f"<td>{_metric(quality.get('system_pii_recall'))}</td>"
            f"<td>{_metric(e2e.get('e2e_pii_recall'))}</td>"
            f"<td>{_metric(e2e.get('e2e_leakage_rate'))}</td>"
            f"<td>{_metric(e2e.get('e2e_zero_leak_document_rate'))}</td>"
            f"<td>{_metric(quality.get('precision'))}</td>"
            f"<td>{_metric(quality.get('inference_success_rate'))}</td>"
            f"<td>{_ms(quality.get('latency_p50_ms'))}</td>"
            "</tr>"
        )

    payload = html.escape(json.dumps(manifest, indent=2, ensure_ascii=False))
    extraction_payload = html.escape(json.dumps(extraction, indent=2, ensure_ascii=False))
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>RedactGuard document E2E benchmark</title>
<style>
body{{font-family:system-ui,sans-serif;margin:40px;max-width:1500px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:right}}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
pre{{background:#f5f5f5;padding:16px;overflow:auto}}
.note{{border-left:4px solid #777;padding:10px 14px;background:#f5f5f5}}
</style></head><body>
<h1>RedactGuard document E2E benchmark</h1>
<p class="note">Evaluation v3 separates model quality on valid inference from system
effectiveness. End-to-end recall/leakage includes both extraction loss and inference
contract failures.</p>
<h2>Extraction</h2>
<pre>{extraction_payload}</pre>
<h2>Models</h2>
<table><thead><tr>
<th>Model</th><th>Contract status</th><th>Quality recall</th><th>System recall</th>
<th>E2E recall</th><th>E2E leakage</th><th>Zero-leak documents</th>
<th>Precision</th><th>Inference success</th><th>p50 ms/page</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Manifest</h2><pre>{payload}</pre>
</body></html>"""
    path.write_text(document, encoding="utf-8")
