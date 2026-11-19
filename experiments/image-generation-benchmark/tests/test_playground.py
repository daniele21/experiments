from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest
from benchmark_core import ArtifactStore, InferenceResult

SCRIPT = Path(__file__).parents[1] / "scripts" / "playground.py"
spec = importlib.util.spec_from_file_location("imagegen_playground", SCRIPT)
assert spec is not None and spec.loader is not None
playground = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playground)

# One valid 1x1 PNG fixture; no image model or API is invoked by these tests.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4"
    "z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
)


class FakeProvider:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def generate(self, request):
        artifact = self.store.persist_bytes(
            artifact_id=request.request_id,
            media_type="image",
            data=TINY_PNG,
            mime_type="image/png",
        )
        return InferenceResult(
            provider_id="korgis-image",
            model_id="qwen-image-2.1-turbo-gguf-q4km",
            raw_output={"created": 1},
            normalized_output={"artifact_id": artifact.artifact_id},
            output_artifacts=(artifact,),
            latency_ms=93.5,
            metadata={"korgis": {"seed": request.generation.seed}},
        )


def test_playground_catalog_uses_existing_model_configuration():
    models = playground.available_models({})
    keys = {entry["key"] for entry in models}
    assert "qwen-image-2.1-turbo-gguf-q4km" in keys
    assert "openai-sunburst" in keys
    turbo = next(entry for entry in models if entry["key"] == "qwen-image-2.1-turbo-gguf-q4km")
    assert turbo["kind"] == "local"
    assert turbo["generation"]["num_inference_steps"] == 8
    assert turbo["configured"] is False
    assert turbo["playground"]["sizes"] == [
        "512x512", "768x768", "1024x1024", "1024x768", "768x1024",
    ]
    assert turbo["playground"]["output_formats"] == ["png", "jpeg", "webp"]
    cloud = next(entry for entry in models if entry["key"] == "openai-sunburst")
    assert cloud["kind"] == "cloud"
    assert not cloud["configured"]


def test_single_playground_generation_persists_png_and_provenance(tmp_path):
    environ = {"KORGIS_BASE_URL": "http://127.0.0.1:1235"}
    observed = []

    def factory(model, *, artifact_store, environ):
        observed.append((model.model_key, environ["KORGIS_BASE_URL"]))
        return FakeProvider(artifact_store)

    result = playground.generate(
        model_key="qwen-image-2.1-turbo-gguf-q4km",
        prompt="A ceramic cup on a table",
        seed=42,
        output_root=tmp_path,
        environ=environ,
        provider_builder=factory,
    )
    assert observed == [("qwen-image-2.1-turbo-gguf-q4km", "http://127.0.0.1:1235")]
    assert result["image_url"] == f"/api/playground/image?id={result['id']}"
    assert result["seed_requested"] == 42
    assert result["seed_effective"] == 42
    assert result["kind"] == "local"
    folder = tmp_path / result["id"]
    assert (folder / "image.png").read_bytes() == TINY_PNG
    assert json.loads((folder / "result.json").read_text())["model_key"] == result["model_key"]
    assert result["generation"]["num_inference_steps"] == 8


def test_playground_rejects_unconfigured_providers(tmp_path):
    with pytest.raises(ValueError, match="missing KORGIS_BASE_URL"):
        playground.generate(
            model_key="qwen-image-2.1-turbo-gguf-q4km",
            prompt="Test", seed=42, output_root=tmp_path,
            environ={}, provider_builder=None,
        )
    assert list(tmp_path.iterdir()) == []


def test_playground_refuses_cloud_seed_and_blank_prompt():
    cloud = playground.require_model("openai-sunburst", {"OPENAI_API_KEY": "dummy"})
    with pytest.raises(ValueError, match="local Korgis"):
        playground.validate("Landscape", 42, cloud)
    local = playground.require_model(
        "qwen-image-2.1-turbo-gguf-q4km",
        {"KORGIS_BASE_URL": "http://127.0.0.1:1235"},
    )
    with pytest.raises(ValueError, match="Prompt"):
        playground.validate(" ", None, local)
    with pytest.raises(ValueError, match="Seed"):
        playground.validate("A nice image", -1, local)


def test_playground_rejects_output_options_not_allowed_for_model():
    validate = playground.resolve_playground_options
    assert validate(
        "qwen-image-2.1-turbo-gguf-q4km", size="768x1024",
        output_format="webp",
    ) == {"size": "768x1024", "output_format": "webp"}
    with pytest.raises(ValueError, match="output size"):
        validate("qwen-image-2.1-turbo-gguf-q4km", size="2048x2048", output_format="png")
    with pytest.raises(ValueError, match="file format"):
        validate("qwen-image-2.1-turbo-gguf-q4km", size="512x512", output_format="svg")
    with pytest.raises(ValueError, match="output size"):
        validate("gemini-pro-image", size="768x1024", output_format=None)
    # Cloud formats not yet verified: a displayed fixed setting must not become
    # an arbitrary provider override.
    assert validate("openai-sunburst", size="1024x1024", output_format="png") == {}


def test_playground_t2i_per_request_options_are_forwarded_and_recorded(tmp_path):
    seen = []
    class PreviewProvider:
        def __init__(self, store):
            self.store = store

        def generate(self, request):
            overrides = dict(request.generation.extra["provider_options"])
            seen.append(overrides)
            assert overrides == {"size": "768x1024", "output_format": "webp"}
            artifact = self.store.persist_bytes(
                artifact_id=request.request_id,
                media_type="image",
                data=b"RIFF" + b"0" * 20 + b"WEBP",
                mime_type="image/webp",
            )
            return InferenceResult(
                provider_id="korgis-image",
                model_id="qwen-image-2.1-turbo-gguf-q4km",
                raw_output={"created": 1},
                normalized_output={"artifact_id": artifact.artifact_id},
                output_artifacts=(artifact,),
                latency_ms=120.0,
                metadata={"korgis": {"seed": request.generation.seed}},
            )

    result = playground.generate(
        model_key="qwen-image-2.1-turbo-gguf-q4km",
        prompt="Portrait with a mountain in the background",
        seed=19345,
        size="768x1024",
        output_format="webp",
        output_root=tmp_path,
        environ={"KORGIS_BASE_URL": "http://127.0.0.1:1235"},
        provider_builder=lambda model, *, artifact_store, environ: PreviewProvider(artifact_store),
    )
    assert seen == [{"size": "768x1024", "output_format": "webp"}]
    assert result["seed_requested"] == 19345
    assert result["seed_effective"] == 19345
    assert result["mime_type"] == "image/webp"
    assert result["generation"]["size"] == "768x1024"
    assert result["generation"]["output_format"] == "webp"
    assert result["filename"] == "image.webp"
    assert (tmp_path / result["id"] / "image.webp").exists()
