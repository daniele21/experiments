from __future__ import annotations

import base64
import csv
import json
from pathlib import Path

from imagegen_bench.reporting import generate_blind_review, generate_identified_report

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZkqsAAAAASUVORK5CYII="
)


def _write_run(
    run_dir: Path,
    *,
    model_keys: tuple[str, ...] = ("model-a", "model-b"),
) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    rows = []
    for model_key in model_keys:
        model_dir = artifacts / model_key
        model_dir.mkdir()
        for prompt_id in ("text-001", "comp-001"):
            image = model_dir / f"{prompt_id}.png"
            image.write_bytes(_TINY_PNG)
            rows.append(
                {
                    "run_id": "run-1",
                    "model_key": model_key,
                    "model_id": f"vendor/{model_key}",
                    "provider_id": "fake",
                    "prompt_id": prompt_id,
                    "category": "text_rendering" if prompt_id.startswith("text") else "compositional",
                    "prompt": f"Prompt for {prompt_id}",
                    "valid": "True",
                    "latency_ms": "12.5",
                    "artifact_id": f"{model_key}-{prompt_id}",
                    "artifact_path": str(image.relative_to(run_dir)),
                    "artifact_sha256": "a" * 64,
                    "error_kind": "",
                    "error_message": "",
                    "generation_config": "{}",
                    "provider_metadata": json.dumps(
                        {
                            "korgis": {
                                "runtime_key": "qwen-image-2.1-mflux-q8",
                                "backend": "mflux_image",
                                "generation": {"quantization_bits": 8},
                            }
                        }
                    ) if model_key == "model-c" else "{}",
                }
            )

    with (run_dir / "evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "requested_models": {"model_keys": list(model_keys)},
                "parameters": {"seed": 42},
            }
        ),
        encoding="utf-8",
    )


def test_identified_report_embeds_images_and_model_names(tmp_path) -> None:
    _write_run(tmp_path)

    output = generate_identified_report(tmp_path, tmp_path / "report.html")

    html = output.read_text(encoding="utf-8")
    assert "model-a" in html
    assert "model-b" in html
    assert "data:image/png;base64," in html
    assert "text-001" in html


def test_blind_review_hides_model_identity_and_writes_separate_key(tmp_path) -> None:
    _write_run(tmp_path)

    output = generate_blind_review(tmp_path, tmp_path / "blind_review.html")

    html = output.read_text(encoding="utf-8")
    assert "Image A" in html
    assert "Image B" in html
    assert "model-a" not in html
    assert "model-b" not in html
    assert "Export votes" in html

    key = json.loads((tmp_path / "blind_key.json").read_text(encoding="utf-8"))
    assert len(key["pairs"]) == 2
    assert {
        key["pairs"][0]["model_for_a"],
        key["pairs"][0]["model_for_b"],
    } == {"model-a", "model-b"}



def test_blind_review_supports_three_model_pairwise_comparison(tmp_path) -> None:
    _write_run(tmp_path, model_keys=("model-a", "model-b", "model-c"))

    output = generate_blind_review(tmp_path, tmp_path / "blind_review.html")

    html = output.read_text(encoding="utf-8")
    assert "model-a" not in html
    assert "model-b" not in html
    assert "model-c" not in html

    key = json.loads((tmp_path / "blind_key.json").read_text(encoding="utf-8"))
    # 2 prompts x C(3, 2) unique model pairs.
    assert len(key["pairs"]) == 6
    for prompt_id in ("text-001", "comp-001"):
        prompt_pairs = [
            row
            for row in key["pairs"]
            if row["prompt_id"] == prompt_id
        ]
        assert len(prompt_pairs) == 3
        assert {
            frozenset((row["model_for_a"], row["model_for_b"]))
            for row in prompt_pairs
        } == {
            frozenset(("model-a", "model-b")),
            frozenset(("model-a", "model-c")),
            frozenset(("model-b", "model-c")),
        }



def test_identified_report_surfaces_korgis_runtime_provenance(tmp_path) -> None:
    _write_run(tmp_path, model_keys=("model-a", "model-b", "model-c"))

    output = generate_identified_report(tmp_path, tmp_path / "report.html")

    html = output.read_text(encoding="utf-8")
    assert "provider=fake" in html
    assert "runtime=qwen-image-2.1-mflux-q8" in html
    assert "backend=mflux_image" in html
    assert "quantization=Q8" in html
