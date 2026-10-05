from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any


@dataclass(frozen=True)
class ShareRenderSummary:
    snapshot_id: str
    output_dir: str
    png_paths: tuple[str, ...]
    pdf_path: str | None
    chrome_binary: str


def _pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value) * 100:.1f}%"


def _pp(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    numeric = float(value) * 100
    sign = "+" if numeric > 0 else ""
    return f"{sign}{numeric:.1f} pp"


def _mb(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value) / (1024 * 1024):.0f} MB"


def _cpu(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value):.1f}%"


def _safe(value: Any) -> str:
    return html.escape(str(value if value is not None else "—"))


def _base_css() -> str:
    return """
:root {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  color: #111827;
  background: #eef1f5;
}
* { box-sizing: border-box; }
html, body { margin: 0; width: 1080px; min-height: 1350px; background: #eef1f5; }
body { overflow: hidden; }
@page { size: 1080px 1350px; margin: 0; }
.card {
  width: 1080px;
  height: 1350px;
  padding: 72px;
  background: #fbfcfe;
  display: flex;
  flex-direction: column;
  page-break-after: always;
  position: relative;
}
.brand {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #425466;
}
.eyebrow {
  margin-top: 70px;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #64748b;
}
h1 {
  margin: 18px 0 22px;
  font-size: 74px;
  line-height: 1.02;
  letter-spacing: -0.045em;
}
h2 {
  margin: 12px 0;
  font-size: 48px;
  line-height: 1.08;
  letter-spacing: -0.035em;
}
p {
  margin: 0;
  font-size: 28px;
  line-height: 1.4;
  color: #52606d;
}
.hero-grid, .quality-grid, .eff-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 26px;
  margin-top: 50px;
}
.panel {
  border: 2px solid #dce2ea;
  border-radius: 28px;
  padding: 34px;
  background: white;
}
.panel span, .metric-label {
  font-size: 22px;
  color: #64748b;
  font-weight: 700;
}
.panel strong {
  display: block;
  margin-top: 16px;
  font-size: 64px;
  letter-spacing: -0.04em;
}
.delta {
  margin-top: 32px;
  padding: 28px 34px;
  border-radius: 24px;
  background: #111827;
  color: white;
  font-size: 34px;
  font-weight: 800;
}
.delta small {
  display: block;
  margin-top: 10px;
  color: #cbd5e1;
  font-size: 20px;
  font-weight: 600;
}
.rows {
  display: grid;
  gap: 16px;
  margin-top: 42px;
}
.row {
  display: grid;
  grid-template-columns: 1.35fr .8fr .8fr;
  gap: 18px;
  align-items: center;
  padding: 20px 0;
  border-bottom: 1px solid #dce2ea;
  font-size: 25px;
}
.row strong { font-size: 24px; }
.row span { color: #52606d; }
.callout {
  margin-top: 44px;
  padding: 28px 32px;
  border-radius: 22px;
  background: #edf7ef;
  color: #166534;
  font-size: 28px;
  line-height: 1.35;
  font-weight: 700;
}
.warning {
  background: #fff7ed;
  color: #9a3412;
}
.footer {
  margin-top: auto;
  padding-top: 28px;
  border-top: 1px solid #dce2ea;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  color: #64748b;
  font-size: 18px;
}
.kv {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 14px 22px;
  margin-top: 42px;
  padding: 32px;
  border: 2px solid #dce2ea;
  border-radius: 24px;
  background: white;
  font-size: 22px;
}
.kv dt { color: #64748b; }
.kv dd { margin: 0; font-weight: 700; overflow-wrap: anywhere; }
.family-row {
  display: grid;
  grid-template-columns: 1.3fr .8fr .8fr;
  gap: 18px;
  padding: 18px 0;
  border-bottom: 1px solid #dce2ea;
  font-size: 24px;
}
.family-row strong { font-size: 23px; }
.tag {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 10px 16px;
  border-radius: 999px;
  background: #e7edf5;
  color: #334155;
  font-size: 18px;
  font-weight: 800;
}
"""


def _shell(body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{_base_css()}</style></head><body>{body}</body></html>"
    )


def _footer(snapshot: dict[str, Any], index: int) -> str:
    return (
        "<div class='footer'>"
        f"<span>Snapshot {_safe(snapshot.get('snapshot_id'))}</span>"
        f"<span>{index}/5 · MCB</span>"
        "</div>"
    )


def _cells(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in snapshot.get("cells") or []
        if isinstance(item, dict)
    ]


def _card_finding(snapshot: dict[str, Any]) -> str:
    cells = _cells(snapshot)
    title = snapshot.get("title") or f"{snapshot.get('capability_id')}: model comparison"
    first = cells[0] if cells else {}
    second = cells[1] if len(cells) > 1 else {}
    comparison = snapshot.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {}
    return _shell(
        "<section class='card'>"
        "<div class='brand'>MCB · Model Capability Benchmark</div>"
        "<div class='eyebrow'>Benchmark finding</div>"
        f"<h1>{_safe(title)}</h1>"
        "<div class='hero-grid'>"
        f"<div class='panel'><span>{_safe(first.get('model_key'))}</span>"
        f"<strong>{_pct(first.get('primary_value'))}</strong>"
        f"<p>{_safe(first.get('primary_metric'))}</p></div>"
        f"<div class='panel'><span>{_safe(second.get('model_key'))}</span>"
        f"<strong>{_pct(second.get('primary_value'))}</strong>"
        f"<p>{_safe(second.get('primary_metric'))}</p></div>"
        "</div>"
        f"<div class='delta'>B − A: {_pp(comparison.get('delta_b_minus_a'))}"
        f"<small>paired n={_safe(comparison.get('paired_count'))} · "
        f"95% CI [{_pp(comparison.get('ci95_low'))}, "
        f"{_pp(comparison.get('ci95_high'))}]</small></div>"
        f"{_footer(snapshot, 1)}"
        "</section>"
    )


def _card_quality(snapshot: dict[str, Any]) -> str:
    cells = _cells(snapshot)
    comparison = snapshot.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {}
    panels = "".join(
        (
            "<div class='panel'>"
            f"<span>{_safe(cell.get('model_key'))}</span>"
            f"<strong>{_pct(cell.get('primary_value'))}</strong>"
            f"<p>n={_safe(cell.get('sample_count'))} · "
            f"failures={_safe(cell.get('failure_count'))}</p>"
            "</div>"
        )
        for cell in cells[:2]
    )
    practical = comparison.get("practical_delta")
    exceeds = comparison.get("exceeds_practical_delta")
    note = (
        "The observed gap exceeds the configured practical threshold."
        if exceeds is True
        else "The observed gap does not exceed the configured practical threshold."
        if exceeds is False
        else "Practical-equivalence evidence is unavailable for this snapshot."
    )
    return _shell(
        "<section class='card'>"
        "<div class='brand'>MCB · Quality</div>"
        "<div class='eyebrow'>Same-case paired comparison</div>"
        "<h2>Quality before speed</h2>"
        "<p>Only evidence from the same benchmark lineage is compared.</p>"
        f"<div class='quality-grid'>{panels}</div>"
        f"<div class='callout'>{_safe(note)} "
        f"Threshold: {_pp(practical)}</div>"
        f"{_footer(snapshot, 2)}"
        "</section>"
    )


def _card_families(snapshot: dict[str, Any]) -> str:
    rows = [
        row
        for row in snapshot.get("family_breakdown") or []
        if isinstance(row, dict)
    ]
    models = list(snapshot.get("model_keys") or [])[:2]
    families = sorted({str(row.get("family") or "") for row in rows if row.get("family")})
    rendered = []
    for family in families[:10]:
        values = []
        for model in models:
            match = next(
                (
                    row
                    for row in rows
                    if row.get("family") == family and row.get("model_key") == model
                ),
                None,
            )
            values.append(_pct(match.get("value") if match else None))
        while len(values) < 2:
            values.append("—")
        rendered.append(
            "<div class='family-row'>"
            f"<strong>{_safe(family)}</strong>"
            f"<span>{_safe(values[0])}</span>"
            f"<span>{_safe(values[1])}</span>"
            "</div>"
        )
    return _shell(
        "<section class='card'>"
        "<div class='brand'>MCB · Failure analysis</div>"
        "<div class='eyebrow'>Where does the gap come from?</div>"
        "<h2>Performance by case family</h2>"
        f"<div class='family-row'><strong>Family</strong>"
        f"<span>{_safe(models[0] if models else 'Model A')}</span>"
        f"<span>{_safe(models[1] if len(models) > 1 else 'Model B')}</span></div>"
        + "".join(rendered)
        + (
            "<div class='callout'>No family breakdown was available.</div>"
            if not rendered
            else ""
        )
        + _footer(snapshot, 3)
        + "</section>"
    )


def _card_efficiency(snapshot: dict[str, Any]) -> str:
    cells = _cells(snapshot)
    execution_signatures = {
        str(cell.get("execution_signature") or "")
        for cell in cells[:2]
        if cell.get("execution_signature")
    }
    comparable = len(cells) >= 2 and len(execution_signatures) == 1
    panels = []
    for cell in cells[:2]:
        resource = cell.get("resource_summary")
        if not isinstance(resource, dict):
            resource = {}
        panels.append(
            "<div class='panel'>"
            f"<span>{_safe(cell.get('model_key'))}</span>"
            f"<strong>{_cpu(resource.get('process_cpu_percent_avg'))}</strong>"
            "<p>CPU avg</p>"
            f"<strong>{_mb(resource.get('process_rss_bytes_peak'))}</strong>"
            "<p>RSS peak</p>"
            "</div>"
        )
    note = (
        "Execution signatures match: runtime resource evidence is comparable."
        if comparable
        else "NON_COMPARABLE: execution signatures differ or resource telemetry is missing."
    )
    cls = "callout" if comparable else "callout warning"
    return _shell(
        "<section class='card'>"
        "<div class='brand'>MCB · Efficiency</div>"
        "<div class='eyebrow'>Local compute evidence</div>"
        "<h2>Quality is only half the decision</h2>"
        "<p>CPU/RAM values are shown only when emitted by the runtime telemetry contract.</p>"
        f"<div class='eff-grid'>{''.join(panels)}</div>"
        f"<div class='{cls}'>{_safe(note)}</div>"
        f"{_footer(snapshot, 4)}"
        "</section>"
    )


def _card_methodology(snapshot: dict[str, Any]) -> str:
    commits = ", ".join(str(value) for value in snapshot.get("git_commits") or [])
    methodology = snapshot.get("methodology")
    if not isinstance(methodology, dict):
        methodology = {}
    return _shell(
        "<section class='card'>"
        "<div class='brand'>MCB · Methodology</div>"
        "<div class='eyebrow'>Reproducibility</div>"
        "<h2>What this result actually means</h2>"
        "<dl class='kv'>"
        f"<dt>Capability</dt><dd>{_safe(snapshot.get('capability_id'))}</dd>"
        f"<dt>Benchmark signature</dt><dd>{_safe(snapshot.get('benchmark_signature'))}</dd>"
        f"<dt>Profile</dt><dd>{_safe(snapshot.get('profile'))}</dd>"
        f"<dt>Run IDs</dt><dd>{_safe(', '.join(snapshot.get('run_ids') or []))}</dd>"
        f"<dt>Git commit(s)</dt><dd>{_safe(commits)}</dd>"
        f"<dt>Paired same cases</dt><dd>{_safe(methodology.get('paired_same_cases'))}</dd>"
        f"<dt>Snapshot ID</dt><dd>{_safe(snapshot.get('snapshot_id'))}</dd>"
        "</dl>"
        "<div class='callout'>The card is rendered only from this immutable snapshot. "
        "Future dashboard updates do not change it.</div>"
        f"{_footer(snapshot, 5)}"
        "</section>"
    )


def build_share_cards(snapshot: dict[str, Any]) -> tuple[str, ...]:
    if str(snapshot.get("schema_version") or "") != "1":
        raise ValueError("unsupported share snapshot schema_version")
    if not str(snapshot.get("snapshot_id") or "").strip():
        raise ValueError("share snapshot requires snapshot_id")
    return (
        _card_finding(snapshot),
        _card_quality(snapshot),
        _card_families(snapshot),
        _card_efficiency(snapshot),
        _card_methodology(snapshot),
    )


def _find_chrome(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.getenv("CHROME_BIN"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    raise FileNotFoundError(
        "Chrome/Chromium was not found. Pass --chrome or set CHROME_BIN."
    )


def _run_browser(
    command: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    runner(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def render_share_snapshot(
    *,
    snapshot_path: Path,
    formats: tuple[str, ...] = ("png", "pdf"),
    chrome_binary: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ShareRenderSummary:
    invalid_formats = sorted(set(formats) - {"png", "pdf"})
    if invalid_formats or not formats:
        raise ValueError(
            "formats must contain one or both of: png, pdf"
        )

    snapshot_path = snapshot_path.resolve()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    cards = build_share_cards(snapshot)
    snapshot_id = str(snapshot["snapshot_id"])
    output_dir = snapshot_path.parent
    chrome = _find_chrome(chrome_binary)
    png_paths: list[str] = []

    if "png" in formats:
        for index, card in enumerate(cards, start=1):
            html_path = output_dir / f".card-{index:02d}.html"
            png_path = output_dir / f"card-{index:02d}.png"
            html_path.write_text(card, encoding="utf-8")
            _run_browser(
                [
                    chrome,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    "--window-size=1080,1350",
                    f"--screenshot={png_path}",
                    html_path.as_uri(),
                ],
                runner=runner,
            )
            html_path.unlink(missing_ok=True)
            if not png_path.is_file():
                raise RuntimeError(f"Chrome did not create {png_path}")
            png_paths.append(str(png_path))

    pdf_path: Path | None = None
    if "pdf" in formats:
        pdf_path = output_dir / "carousel.pdf"
        deck_path = output_dir / ".carousel.html"
        bodies = []
        for card in cards:
            start = card.find("<body>") + len("<body>")
            end = card.rfind("</body>")
            bodies.append(card[start:end])
        deck_path.write_text(_shell("".join(bodies)), encoding="utf-8")
        _run_browser(
            [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--print-to-pdf-no-header",
                f"--print-to-pdf={pdf_path}",
                deck_path.as_uri(),
            ],
            runner=runner,
        )
        deck_path.unlink(missing_ok=True)
        if not pdf_path.is_file():
            raise RuntimeError(f"Chrome did not create {pdf_path}")

    return ShareRenderSummary(
        snapshot_id=snapshot_id,
        output_dir=str(output_dir),
        png_paths=tuple(png_paths),
        pdf_path=str(pdf_path) if pdf_path is not None else None,
        chrome_binary=chrome,
    )
