from __future__ import annotations

import json
from pathlib import Path

from model_capability_bench import load_capability_suite
from model_capability_bench.runner import RunnerConfig, RunnerSummary
from model_capability_bench.runner.config import load_runner_defaults
from model_capability_bench.runner.manifest import write_run_artifacts

ROOT = Path(__file__).resolve().parents[1]


def test_runner_defaults_are_configuration_driven() -> None:
    defaults = load_runner_defaults(ROOT)

    assert defaults.output_root == ROOT / "results/runs"
    assert defaults.cache_dir == ROOT / ".cache/datasets"
    assert defaults.default_profile == "smoke"
    assert defaults.default_seed == 42
    assert defaults.resume is True
    assert defaults.retry_failures is False


def test_run_manifest_contains_config_checksums_and_semantic_selection(
    tmp_path: Path,
) -> None:
    bundle = load_capability_suite(ROOT)
    config = RunnerConfig(
        run_group="fixture",
        profile="smoke",
        model_keys=("qwen3.5-2b-q4km", "gpt-5.6-luna"),
        capability_ids=("structured-output", "mathematical-reasoning"),
        seed=7,
    )
    summary = RunnerSummary(
        run_id="run-1",
        run_group="fixture",
        planned_cases=44,
        completed_cases=44,
        failed_cases=0,
        skipped_cases=0,
        model_failures=0,
        aggregate_count=22,
        output_dir=str(tmp_path),
        metadata={
            "signatures": {
                "models": {
                    "qwen3.5-2b-q4km": "sha256:model:qwen",
                    "gpt-5.6-luna": "sha256:model:gpt",
                },
                "executions": {
                    "qwen3.5-2b-q4km": "sha256:execution:qwen",
                    "gpt-5.6-luna": "sha256:execution:gpt",
                },
                "execution_metadata": {
                    "qwen3.5-2b-q4km": {
                        "runtime_source": "korgis",
                        "runtime_identity": {
                            "fingerprint": "a" * 64,
                            "identity": {
                                "backend": {
                                    "name": "llama_server",
                                    "version": "build-10709@prism123",
                                }
                            },
                        },
                    },
                    "gpt-5.6-luna": {},
                },
                "benchmarks": {
                    "structured-output": "sha256:benchmark:structured",
                    "mathematical-reasoning": "sha256:benchmark:math",
                },
            }
        },
    )

    write_run_artifacts(
        suite=bundle,
        config=config,
        summary=summary,
        output_dir=tmp_path,
    )

    environment = json.loads((tmp_path / "environment.json").read_text())
    manifest = json.loads((tmp_path / "run_manifest.json").read_text())

    assert environment["parameters"]["run_id"] == "run-1"
    assert environment["parameters"]["seed"] == 7
    assert environment["pricing"]["as_of"] == "2026-09-20"
    assert environment["pricing"]["currency"] == "USD"
    assert manifest["run"]["run_id"] == "run-1"
    assert manifest["evidence"]["resource_samples"] == "resource_samples.jsonl"
    assert manifest["evidence"]["resource_summary"] == "resource_summary.jsonl"
    assert {model["model_key"] for model in manifest["models"]} == {
        "qwen3.5-2b-q4km",
        "gpt-5.6-luna",
    }
    assert {
        capability["capability_id"]
        for capability in manifest["capabilities"]
    } == {"structured-output", "mathematical-reasoning"}
    for capability in manifest["capabilities"]:
        assert "benchmark" in capability
        assert "comparison" in capability
        assert capability["benchmark_signature"]
    assert manifest["signatures"]["models"]["qwen3.5-2b-q4km"] == (
        "sha256:model:qwen"
    )
    assert {
        model["model_signature"]
        for model in manifest["models"]
    } == {"sha256:model:qwen", "sha256:model:gpt"}
    qwen = next(
        model for model in manifest["models"]
        if model["model_key"] == "qwen3.5-2b-q4km"
    )
    assert qwen["execution_metadata"]["runtime_source"] == "korgis"
    assert (
        qwen["execution_metadata"]["runtime_identity"]["identity"]["backend"]["version"]
        == "build-10709@prism123"
    )
    assert set(manifest["config_checksums"]) == {
        "models.yaml",
        "tasks.yaml",
        "datasets.yaml",
        "profiles.yaml",
        "suite.yaml",
        "runner.yaml",
        "reporting.yaml",
        "pricing_snapshot.json",
    }
