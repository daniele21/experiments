from __future__ import annotations

import json
from pathlib import Path

from benchmark_core import ArtifactStore, InferenceRequest, InferenceResult

from imagegen_bench.config import ResolvedImageModel
from imagegen_bench.planning import build_run_plan
from imagegen_bench.runner import execute_run_plan


ROOT = Path(__file__).parents[1]


class FakeImageProvider:
    provider_id = "fake-image"

    def __init__(
        self,
        model: ResolvedImageModel,
        store: ArtifactStore,
    ) -> None:
        self.model = model
        self.store = store

    def generate(self, request: InferenceRequest) -> InferenceResult:
        artifact = self.store.persist_bytes(
            artifact_id=f"{request.request_id}-0",
            media_type="image",
            data=f"image:{request.request_id}".encode(),
            mime_type="image/png",
        )
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model.model_id,
            raw_output={"fake": True},
            normalized_output={"artifact_id": artifact.artifact_id},
            output_artifacts=(artifact,),
            latency_ms=1.0,
        )


def fake_provider_factory(model, store, environ):
    del environ
    return FakeImageProvider(model, store)


def test_runner_persists_incremental_evidence_artifacts_and_manifest(tmp_path) -> None:
    plan = build_run_plan(
        ROOT,
        model_keys=["openai-sunburst"],
        profile_id="smoke",
    )

    rows = execute_run_plan(
        plan,
        output_dir=tmp_path,
        environ={},
        provider_factory=fake_provider_factory,
    )

    assert len(rows) == 4
    assert all(row["valid"] for row in rows)
    run_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "evidence.csv").is_file()
    assert len(list((run_dir / "artifacts" / "openai-sunburst").iterdir())) == 4

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["suite"] == "imagegen-core-v1"
    assert manifest["parameters"]["profile"] == "smoke"
    assert len(manifest["parameters"]["prompt_ids"]) == 4
