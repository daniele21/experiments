from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from benchmark_core import ArtifactStore, InferenceRequest, InferenceResult
from imagegen_bench.config import ResolvedImageModel
from imagegen_bench.planning import build_run_plan
from imagegen_bench.runner import execute_run_plan

ROOT = Path(__file__).parents[1]


class SeedRecordingProvider:
    def __init__(self, model: ResolvedImageModel, store: ArtifactStore, seen: list):
        self.model = model
        self.store = store
        self.seen = seen

    def generate(self, request: InferenceRequest) -> InferenceResult:
        self.seen.append(request)
        artifact = self.store.persist_bytes(
            artifact_id=request.request_id,
            media_type="image",
            data=f"tiny:{request.request_id}".encode(),
            mime_type="image/png",
        )
        return InferenceResult(
            provider_id="fake-image",
            model_id=self.model.model_id,
            raw_output={"test": True},
            normalized_output={"artifact_id": artifact.artifact_id},
            output_artifacts=(artifact,),
            latency_ms=10.0,
            metadata={"korgis": {"seed": request.generation.seed}},
        )


def test_repeat_samples_are_unique_and_seeds_reach_korgis(tmp_path):
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen-image-2.1-turbo-gguf-q4km"],
        profile_id="smoke",
    )
    plan = replace(plan, outputs_per_prompt=3)
    observed: list[InferenceRequest] = []

    def factory(model, store, env):
        del env
        # Manifest exists even before the first provider is initialized.
        assert len(list(tmp_path.glob("*/manifest.json"))) == 1
        return SeedRecordingProvider(model, store, observed)

    rows = execute_run_plan(
        plan, output_dir=tmp_path,
        environ={}, provider_factory=factory,
    )
    assert len(rows) == 12  # 4 smoke prompts x 3 outputs
    assert len({row["artifact_id"] for row in rows}) == 12
    assert len({row["artifact_sha256"] for row in rows}) == 12
    assert all(row["valid"] for row in rows)
    assert sorted(set(row["sample_index"] for row in rows)) == [0, 1, 2]
    assert sorted(set(row["seed_requested"] for row in rows)) == [42, 43, 44]
    assert sorted(set(row["seed_effective"] for row in rows)) == [42, 43, 44]
    assert [r.generation.seed for r in observed[:3]] == [42, 43, 44]

    run_dir = next(path for path in tmp_path.iterdir() if path.is_dir())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["parameters"]["outputs_per_prompt"] == 3
    assert len(list((run_dir / "artifacts" / plan.models[0].model_key).iterdir())) == 12


def test_cloud_arm_does_not_claim_deterministic_seed_support(tmp_path):
    plan = build_run_plan(
        ROOT, model_keys=["openai-sunburst"], profile_id="smoke",
    )
    seen: list[InferenceRequest] = []

    def factory(model, store, env):
        return SeedRecordingProvider(model, store, seen)

    rows = execute_run_plan(
        plan, output_dir=tmp_path, environ={},
        provider_factory=factory,
    )
    assert len(rows) == 4
    assert all(r["seed_requested"] is None for r in rows)
    assert all(r.generation.seed is None for r in seen)


def test_robust_profile_is_configured_for_three_samples():
    plan = build_run_plan(
        ROOT, model_keys=["qwen-image-2.1-turbo-gguf-q4km"],
        profile_id="robust",
    )
    assert len(plan.prompts) == 20
    assert plan.outputs_per_prompt == 3
