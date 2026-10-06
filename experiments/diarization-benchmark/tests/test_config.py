from pathlib import Path

from diarization_bench.config import load_manifest, load_models, select_models


ROOT = Path(__file__).resolve().parents[1]


def test_model_registry_contains_core_candidates() -> None:
    models = load_models(ROOT / "models.yaml")

    assert {
        "community-1-vbx",
        "sortformer-v2.1-balanced",
        "ls-eend-dihard3-500ms",
        "nemotron3-fast32",
        "nemotron3-offline",
    } <= set(models)
    assert models["sortformer-v2.1-balanced"].max_speakers == 4
    assert models["nemotron3-fast32"].max_speakers == 8


def test_manifest_schema(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
cases:
  - id: one
    audio: /tmp/audio.wav
    reference_rttm: /tmp/reference.rttm
    tags:
      overlap: low
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cases = load_manifest(manifest)

    assert [case.case_id for case in cases] == ["one"]
    assert cases[0].tags["overlap"] == "low"


def test_model_selection_is_explicit() -> None:
    models = load_models(ROOT / "models.yaml")
    selected = select_models(models, "community-1-vbx,nemotron3-fast32")

    assert [model.key for model in selected] == ["community-1-vbx", "nemotron3-fast32"]
