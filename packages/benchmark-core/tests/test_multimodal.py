from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import (
    ArtifactStore,
    CapabilityMismatchError,
    ContentPart,
    InferenceRequest,
    InferenceResult,
    MediaRef,
    ModelCapabilities,
    ModelSpec,
    RawInferenceRecord,
    validate_model_capabilities,
)


def _image_ref() -> MediaRef:
    return MediaRef(
        media_id="fixture-image",
        media_type="image",
        location="fixtures/example.png",
        mime_type="image/png",
        sha256="a" * 64,
        width=32,
        height=24,
    )


def test_multimodal_request_accepts_typed_content_without_breaking_text_input() -> None:
    image = _image_ref()
    request = InferenceRequest(
        request_id="vlm-1",
        content=(
            ContentPart(kind="text", text="What is visible?"),
            ContentPart(kind="image", media=image),
        ),
    )
    text_request = InferenceRequest(request_id="text-1", input="hello")

    assert request.content[1].media == image
    assert text_request.input == "hello"


def test_media_contract_rejects_mismatched_mime_and_part_kind() -> None:
    with pytest.raises(ValueError, match="image/"):
        MediaRef(
            media_id="bad",
            media_type="image",
            location="fixture.txt",
            mime_type="text/plain",
            sha256="b" * 64,
        )

    with pytest.raises(ValueError, match="does not match"):
        ContentPart(
            kind="document",
            media=_image_ref(),
        )


def test_artifact_store_is_content_addressed_and_stable(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    payload = b"synthetic-image-bytes"

    first = store.persist_bytes(
        artifact_id="generated-1",
        media_type="image",
        data=payload,
        mime_type="image/png",
        width=64,
        height=64,
    )
    second = store.persist_bytes(
        artifact_id="generated-2",
        media_type="image",
        data=payload,
        mime_type="image/png",
        width=64,
        height=64,
    )

    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert Path(first.path).read_bytes() == payload
    assert first.size_bytes == len(payload)


def test_register_input_captures_checksum(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    source.write_bytes(b"input-image")
    store = ArtifactStore(tmp_path / "artifacts")

    media = store.register_input(
        path=source,
        media_id="input-1",
        media_type="image",
        mime_type="image/png",
    )

    assert media.location == str(source)
    assert len(media.sha256) == 64


def test_model_capability_preflight_fails_before_inference() -> None:
    text_model = ModelSpec(
        model_key="text-only",
        model_id="vendor/text-only",
        runtime_key="api",
    )
    image_model = ModelSpec(
        model_key="vlm",
        model_id="vendor/vlm",
        runtime_key="api",
        capabilities=ModelCapabilities(image_input=True, multi_image_input=True),
    )
    required = ModelCapabilities(image_input=True)

    with pytest.raises(CapabilityMismatchError, match="image_input"):
        validate_model_capabilities(text_model, required)

    validate_model_capabilities(image_model, required)


def test_generated_artifacts_flow_into_raw_inference_records(tmp_path: Path) -> None:
    artifact = ArtifactStore(tmp_path).persist_bytes(
        artifact_id="image-1",
        media_type="image",
        data=b"generated",
        mime_type="image/png",
    )
    result = InferenceResult(
        provider_id="fake-image-provider",
        model_id="fake-image-model",
        raw_output={"status": "ok"},
        output_artifacts=(artifact,),
        latency_ms=12.0,
    )

    record = RawInferenceRecord.from_inference_result(
        run_id="run-1",
        run_group="group-1",
        suite_id="imagegen",
        task_id="text-to-image",
        sample_id="prompt-1",
        result=result,
    )

    assert record.output_artifacts == (artifact,)
    assert record.output_artifacts[0].sha256 == artifact.sha256
