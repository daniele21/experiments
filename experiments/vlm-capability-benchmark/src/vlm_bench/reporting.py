from __future__ import annotations

import base64
import csv
import json
import mimetypes
from collections import defaultdict
from html import escape
from pathlib import Path


def _load_rows(run_dir: Path) -> list[dict[str, str]]:
    evidence = run_dir / "evidence.csv"
    if not evidence.is_file():
        raise FileNotFoundError(f"evidence file not found: {evidence}")
    with evidence.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _resolve_input(run_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = run_dir / path
    if not path.is_file():
        raise FileNotFoundError(f"input evidence not found: {path}")
    return path


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _parse_box(raw: str) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("target_box evidence must contain four coordinates")
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def _overlay_html(row: dict[str, str]) -> str:
    box = _parse_box(row.get("target_box", ""))
    overlays: list[str] = []
    if box is not None:
        x_min, y_min, x_max, y_max = box
        overlays.append(
            '<div class="truth" style="'
            f"left:{x_min * 100:.3f}%;top:{y_min * 100:.3f}%;"
            f"width:{(x_max - x_min) * 100:.3f}%;"
            f"height:{(y_max - y_min) * 100:.3f}%"
            '"></div>'
        )

    if row.get("prediction_x") and row.get("prediction_y"):
        x = float(row["prediction_x"])
        y = float(row["prediction_y"])
        overlays.append(
            '<div class="marker" style="'
            f"left:{x * 100:.3f}%;top:{y * 100:.3f}%"
            '"></div>'
        )
    return "".join(overlays)


def generate_vlm_report(run_dir: Path, output_path: Path) -> Path:
    rows = _load_rows(run_dir)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["sample_id"]].append(row)

    sections: list[str] = []
    for sample_id in sorted(grouped):
        sample_rows = grouped[sample_id]
        question = sample_rows[0].get("question", "")
        target = sample_rows[0].get("target_label", "")
        model_cards: list[str] = []

        for row in sorted(sample_rows, key=lambda item: item["model_key"]):
            image_url = _image_data_url(
                _resolve_input(run_dir, row["input_asset_path"])
            )
            model_cards.append(
                f"""<article class="output">
<div class="visual">
<img src="{image_url}" alt="{escape(sample_id)}">
{_overlay_html(row)}
</div>
<div class="meta">
<strong>{escape(row["model_key"])}</strong><br>
<span>prediction: {escape(row.get("prediction_target", ""))}</span><br>
<span class="badge">hit={escape(row.get("click_hit", ""))}</span>
<span class="badge">label={escape(row.get("target_match", ""))}</span>
<span class="badge">distance={escape(row.get("point_distance", ""))}</span>
<span class="badge">{escape(row.get("latency_ms", ""))} ms</span>
</div>
</article>"""
            )

        sections.append(
            f"""<section class="card">
<h2>{escape(sample_id)}</h2>
<p><strong>Goal:</strong> {escape(question)}</p>
<p><strong>Ground truth:</strong> {escape(target)}</p>
<div class="legend"><span class="truth-key"></span> target box
<span class="marker-key"></span> predicted click</div>
<div class="grid">{''.join(model_cards)}</div>
</section>"""
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VLM grounding benchmark</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #16181d; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 32px 20px 64px; }}
.card {{ background: white; border: 1px solid #dfe3e8; border-radius: 14px;
         padding: 18px; margin-bottom: 22px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
         gap: 16px; }}
.output {{ border: 1px solid #e3e6ea; border-radius: 12px; overflow: hidden; }}
.visual {{ position: relative; background: #eef1f4; }}
.visual img {{ width: 100%; display: block; }}
.truth {{ position: absolute; border: 3px solid #16803a; box-sizing: border-box;
          pointer-events: none; }}
.marker {{ position: absolute; width: 16px; height: 16px; border-radius: 50%;
           border: 3px solid white; background: #d92d20;
           transform: translate(-50%, -50%); box-sizing: border-box; }}
.meta {{ padding: 12px; font-size: 14px; }}
.badge {{ display: inline-block; border: 1px solid #cfd4da; border-radius: 999px;
          padding: 3px 8px; margin: 6px 4px 0 0; font-size: 12px; }}
.legend {{ font-size: 13px; margin-bottom: 12px; color: #606975; }}
.truth-key {{ display: inline-block; width: 16px; height: 10px;
              border: 2px solid #16803a; margin-right: 4px; }}
.marker-key {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%;
               background: #d92d20; margin: 0 4px 0 14px; }}
</style>
</head>
<body>
<main>
<h1>VLM grounding benchmark</h1>
{''.join(sections)}
</main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
