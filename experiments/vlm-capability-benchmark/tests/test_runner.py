from __future__ import annotations

import json
from pathlib import Path

from benchmark_core import InferenceRequest, InferenceResult

from vlm_bench.config import ResolvedVLMModel
from vlm_bench.planning import build_run_plan
from vlm_bench.runner import execute_run_plan

ROOT = Path(__file__).parents[1]


class FakeVLMProvider:
    provider_id = "fake-vlm"

    def __init__(self, model: ResolvedVLMModel) -> None:
        self.model = model

    def generate(self, request: InferenceRequest) -> InferenceResult:
        predictions = {
            "ui-create-project-001": '{"target":"Create project","x":0.86,"y":0.12}',
            "ui-settings-001": '{"target":"Settings","x":0.11,"y":0.89}',
        }
        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model.model_id,
            raw_output={"fake": True},
            normalized_output=predictions[request.request_id],
            latency_ms=1.0,
        )


def fake_provider_factory(model, environ):
    del environ
    return FakeVLMProvider(model)


def test_vlm_smoke_plan_is_deterministic() -> None:
    first = build_run_plan(
        ROOT,
        model_keys=["qwen3-vl-4b-instruct"],
        profile_id="smoke",
    )
    second = build_run_plan(
        ROOT,
        model_keys=["qwen3-vl-4b-instruct"],
        profile_id="smoke",
    )

    assert first == second
    assert first.task_id == "ui_grounding"
    assert len(first.cases) == 2
    assert first.prompt_sha256
    assert first.models[0].runtime_key == "korgis-local"
    assert first.models[0].provider_key == "korgis-openai-compatible"
    assert first.models[0].model_id == "qwen3-vl-4b"


def test_vlm_runner_persists_grounding_evidence_and_manifest(tmp_path) -> None:
    plan = build_run_plan(
        ROOT,
        model_keys=["qwen3-vl-4b-instruct"],
        profile_id="smoke",
    )

    rows = execute_run_plan(
        plan,
        output_dir=tmp_path,
        environ={},
        provider_factory=fake_provider_factory,
    )

    assert len(rows) == 2
    assert all(row["valid"] for row in rows)
    assert all(row["click_hit"] for row in rows)
    assert all(row["target_match"] for row in rows)

    run_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "evidence.csv").is_file()
    input_files = list((run_dir / "inputs").iterdir())
    assert len(input_files) == 2
    assert all(path.is_file() for path in input_files)
    assert all(row["input_asset_path"].startswith("inputs/") for row in rows)
    assert all(row["input_asset_sha256"] for row in rows)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["suite"] == "vlm-core-v1"
    assert manifest["parameters"]["task_id"] == "ui_grounding"
    assert manifest["parameters"]["evaluator_id"] == "ui_grounding_v1"
    assert len(manifest["parameters"]["sample_ids"]) == 2
