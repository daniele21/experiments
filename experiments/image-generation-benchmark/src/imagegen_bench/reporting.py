from __future__ import annotations

import base64
import csv
import json
import mimetypes
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

from imagegen_bench.human_eval import build_blind_pair


def _load_rows(run_dir: Path) -> list[dict[str, str]]:
    evidence = run_dir / "evidence.csv"
    if not evidence.is_file():
        raise FileNotFoundError(f"evidence file not found: {evidence}")
    with evidence.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"manifest file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def _resolve_artifact(run_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = run_dir / path
    if not path.is_file():
        raise FileNotFoundError(f"generated artifact not found: {path}")
    return path


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _page(title: str, body: str, *, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #16181d; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 32px 20px 64px; }}
header {{ margin-bottom: 28px; }}
.card {{ background: white; border: 1px solid #dfe3e8; border-radius: 14px;
         padding: 18px; margin-bottom: 22px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
         gap: 16px; }}
.output {{ border: 1px solid #e3e6ea; border-radius: 12px; overflow: hidden; background: #fff; }}
.output img {{ width: 100%; display: block; aspect-ratio: 1 / 1; object-fit: contain;
               background: #f1f3f5; }}
.meta {{ padding: 12px; font-size: 14px; }}
.prompt {{ white-space: pre-wrap; line-height: 1.45; }}
.badge {{ display: inline-block; border: 1px solid #cfd4da; border-radius: 999px;
          padding: 3px 8px; margin-right: 6px; font-size: 12px; }}
.vote {{ padding: 12px; border-top: 1px solid #e3e6ea; }}
.vote label {{ margin-right: 14px; }}
button {{ padding: 10px 16px; border-radius: 8px; border: 1px solid #aab2bb;
          background: white; cursor: pointer; }}
.small {{ color: #606975; font-size: 13px; }}
</style>
</head>
<body>
<main>
<header><h1>{escape(title)}</h1></header>
{body}
</main>
{script}
</body>
</html>
"""


def generate_identified_report(run_dir: Path, output_path: Path) -> Path:
    rows = _load_rows(run_dir)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["prompt_id"]].append(row)

    sections: list[str] = []
    for prompt_id in sorted(grouped):
        prompt_rows = grouped[prompt_id]
        prompt = prompt_rows[0].get("prompt", "")
        category = prompt_rows[0].get("category", "")
        outputs: list[str] = []

        for row in sorted(prompt_rows, key=lambda item: item["model_key"]):
            if row.get("artifact_path"):
                image_url = _image_data_url(
                    _resolve_artifact(run_dir, row["artifact_path"])
                )
                image_html = f'<img src="{image_url}" alt="{escape(row["model_key"])} output">'
            else:
                image_html = '<div class="meta">No generated artifact</div>'

            outputs.append(
                f"""<article class="output">
{image_html}
<div class="meta">
<strong>{escape(row["model_key"])}</strong><br>
<span class="small">{escape(row.get("model_id", ""))}</span><br>
<span class="badge">{escape(row.get("latency_ms", ""))} ms</span>
<span class="badge">valid={escape(row.get("valid", ""))}</span>
</div>
</article>"""
            )

        sections.append(
            f"""<section class="card">
<h2>{escape(prompt_id)} · {escape(category)}</h2>
<p class="prompt">{escape(prompt)}</p>
<div class="grid">{''.join(outputs)}</div>
</section>"""
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _page("Image generation benchmark", "".join(sections)),
        encoding="utf-8",
    )
    return output_path


def generate_blind_review(run_dir: Path, output_path: Path) -> Path:
    rows = _load_rows(run_dir)
    manifest = _load_manifest(run_dir)
    parameters = manifest.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("manifest parameters must be an object")

    model_keys = manifest.get("requested_models", {}).get("model_keys", [])
    if not isinstance(model_keys, list) or len(model_keys) != 2:
        raise ValueError("blind review currently requires exactly two requested models")
    first_model, second_model = (str(model_keys[0]), str(model_keys[1]))
    seed = int(parameters.get("seed", 0))

    by_prompt: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        by_prompt[row["prompt_id"]][row["model_key"]] = row

    sections: list[str] = []
    pair_metadata: list[dict[str, str]] = []
    for prompt_id in sorted(by_prompt):
        model_rows = by_prompt[prompt_id]
        if first_model not in model_rows or second_model not in model_rows:
            continue

        pair = build_blind_pair(
            prompt_id=prompt_id,
            first_model=first_model,
            second_model=second_model,
            seed=seed,
        )
        row_a = model_rows[pair.model_for_a]
        row_b = model_rows[pair.model_for_b]
        if not row_a.get("artifact_path") or not row_b.get("artifact_path"):
            continue

        image_a = _image_data_url(_resolve_artifact(run_dir, row_a["artifact_path"]))
        image_b = _image_data_url(_resolve_artifact(run_dir, row_b["artifact_path"]))
        prompt = row_a.get("prompt", "")
        category = row_a.get("category", "")
        pair_metadata.append(
            {
                "pair_id": pair.pair_id,
                "prompt_id": prompt_id,
                "model_for_a": pair.model_for_a,
                "model_for_b": pair.model_for_b,
            }
        )

        criteria = []
        for criterion in ("prompt_adherence", "visual_preference", "text_quality"):
            inputs = "".join(
                f'<label><input type="radio" name="{pair.pair_id}:{criterion}" '
                f'value="{choice}"> {choice}</label>'
                for choice in ("A", "B", "tie")
            )
            criteria.append(
                f'<div class="vote"><strong>{criterion}</strong><br>{inputs}</div>'
            )

        sections.append(
            f"""<section class="card" data-pair-id="{pair.pair_id}"
data-prompt-id="{escape(prompt_id)}">
<h2>{escape(prompt_id)} · {escape(category)}</h2>
<p class="prompt">{escape(prompt)}</p>
<div class="grid">
<article class="output"><img src="{image_a}" alt="Blind image A">
<div class="meta"><strong>Image A</strong></div></article>
<article class="output"><img src="{image_b}" alt="Blind image B">
<div class="meta"><strong>Image B</strong></div></article>
</div>
{''.join(criteria)}
</section>"""
        )

    metadata_json = json.dumps(pair_metadata).replace("</", "<\/")
    script = f"""<script>
const pairMetadata = {metadata_json};
function exportVotes() {{
  const votes = [];
  for (const pair of pairMetadata) {{
    for (const criterion of ["prompt_adherence", "visual_preference", "text_quality"]) {{
      const name = pair.pair_id + ":" + criterion;
      const selected = document.querySelector('input[name="' + name + '"]:checked');
      if (selected) {{
        votes.push({{
          pair_id: pair.pair_id,
          prompt_id: pair.prompt_id,
          criterion: criterion,
          choice: selected.value
        }});
      }}
    }}
  }}
  const payload = JSON.stringify({{pairs: pairMetadata, votes: votes}}, null, 2);
  const blob = new Blob([payload], {{type: "application/json"}});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "blind_votes.json";
  link.click();
  URL.revokeObjectURL(link.href);
}}
</script>"""

    body = (
        '<div class="card"><p>Model identities are hidden. '
        'Complete the votes and export the JSON when finished.</p>'
        '<button onclick="exportVotes()">Export votes</button></div>'
        + "".join(sections)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _page("Blind image comparison", body, script=script),
        encoding="utf-8",
    )
    return output_path
