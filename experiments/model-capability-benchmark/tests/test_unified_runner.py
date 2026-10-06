from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

from benchmark_core import (
    InferenceError,
    InferenceRequest,
    InferenceResult,
    ResolvedModel,
    TokenUsage,
    read_jsonl_records,
)

from model_capability_bench import load_capability_suite
from model_capability_bench.runner import CapabilityRunner, EvidenceStore, RunnerConfig

ROOT = Path(__file__).resolve().parents[1]


class _FakeProvider:
    provider_id = "fake"

    def __init__(
        self,
        model_id: str,
        *,
        fail_sample_ids: set[str] | None = None,
    ) -> None:
        self.model_id = model_id
        self.fail_sample_ids = fail_sample_ids or set()

    @staticmethod
    def _schema_value(schema: dict) -> object:
        kind = schema.get("type")
        if kind == "string":
            enum = schema.get("enum")
            return enum[0] if isinstance(enum, list) and enum else "fixture"
        if kind == "number":
            return 1.0
        if kind == "integer":
            return 1
        if kind == "boolean":
            return True
        return None

    def generate(self, request: InferenceRequest) -> InferenceResult:
        sample_id = request.request_id.rsplit(":", 1)[-1]
        if sample_id in self.fail_sample_ids:
            raise RuntimeError(f"forced provider failure for {sample_id}")

        task_id = str(request.task_metadata["task_id"])
        if task_id == "structured-output":
            properties = dict((request.response_schema or {}).get("properties") or {})
            output = {
                name: self._schema_value(dict(schema))
                for name, schema in properties.items()
            }
        elif task_id == "qa-abstention":
            output = {"answer": "", "abstain": True}
        elif task_id == "mathematical-reasoning":
            output = {"answer": "0"}
        else:
            output = {"label": "other", "confidence": 0.5}

        return InferenceResult(
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_output=output,
            normalized_output=output,
            latency_ms=2.0,
            usage=TokenUsage(input_tokens=10, output_tokens=3),
            estimated_cost_usd=0.001,
        )


@dataclass
class _FakeRuntime:
    fail_sample_ids: set[str] = field(default_factory=set)
    prepare_calls: list[str] = field(default_factory=list)
    release_calls: list[str] = field(default_factory=list)

    def prepare(self, model: ResolvedModel) -> _FakeProvider:
        self.prepare_calls.append(model.model.model_key)
        return _FakeProvider(
            model.effective_model_id,
            fail_sample_ids=self.fail_sample_ids,
        )

    def execution_metadata(self, model: ResolvedModel) -> dict[str, object]:
        return {
            "runtime_source": "fixture",
            "runtime_key": model.effective_model_id,
            "runtime_identity": {
                "fingerprint": f"fixture-{model.model.model_key}",
            },
        }

    def release(self, model: ResolvedModel) -> None:
        self.release_calls.append(model.model.model_key)


def _runner(
    tmp_path: Path,
    *,
    runtime: _FakeRuntime,
) -> CapabilityRunner:
    bundle = load_capability_suite(ROOT)
    return CapabilityRunner(
        suite=bundle,
        runtime_resolver=lambda model: runtime,
        evidence_store=EvidenceStore(tmp_path / "evidence"),
        cache_dir=tmp_path / "cache",
        environ={
            "KORGIS_BASE_URL": "http://fake.local/v1",
            "OPENAI_API_KEY": "fake-key",
        },
    )


def test_cli_live_progress_preserves_json_and_tracks_resume(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    import json
    import sys

    from model_capability_bench.cli import main

    runtime = _FakeRuntime()
    monkeypatch.setenv("KORGIS_BASE_URL", "http://fake.local/v1")
    monkeypatch.setattr(
        "model_capability_bench.cli.RegistryRuntimeResolver",
        lambda environ: lambda model: runtime,
    )
    arguments = [
        "model-bench", "run", "--run-group", "progress-test",
        "--run-id", "progress-test", "--models", "qwen3.5-2b-q4km",
        "--capabilities", "structured-output", "--profile", "smoke",
        "--output-dir", str(tmp_path / "evidence"),
        "--cache-dir", str(tmp_path / "cache"),
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    assert main() == 0
    first = capsys.readouterr()
    assert json.loads(first.out)["summary"]["completed_cases"] == 12
    assert "12/12 100%" in first.err
    assert "COMPLETED" in first.err
    assert "ETA" in first.err
    events = read_jsonl_records(tmp_path / "evidence" / "events.jsonl")
    start = next(event for event in events if event["event_type"] == "capability.started")
    assert start["metadata"]["planned_cases"] == 12

    assert main() == 0
    resumed = capsys.readouterr()
    assert json.loads(resumed.out)["summary"]["skipped_cases"] == 12
    assert "12/12 100%" in resumed.err
    assert "ok 0 failed 0 resumed 12" in resumed.err

    monkeypatch.setattr(sys, "argv", [*arguments, "--no-progress"])
    assert main() == 0
    silent = capsys.readouterr()
    assert json.loads(silent.out)["summary"]["skipped_cases"] == 12
    assert silent.err == ""


def test_unified_runner_executes_two_models_and_resumes(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    runner = _runner(tmp_path, runtime=runtime)
    config = RunnerConfig(
        run_group="fixture-run",
        profile="smoke",
        model_keys=("qwen3.5-2b-q4km", "gpt-5.6-luna"),
        capability_ids=(
            "structured-output",
            "qa-abstention",
            "mathematical-reasoning",
        ),
        seed=42,
    )

    first = runner.run(config)

    assert first.planned_cases == 72
    assert first.completed_cases == 72
    assert first.failed_cases == 0
    assert first.skipped_cases == 0
    assert first.model_failures == 0
    assert first.aggregate_count == 38
    assert runtime.prepare_calls == ["qwen3.5-2b-q4km", "gpt-5.6-luna"]
    assert runtime.release_calls == runtime.prepare_calls

    root = tmp_path / "evidence"
    assert len(read_jsonl_records(root / "raw.jsonl")) == 72
    assert len(read_jsonl_records(root / "evaluation.jsonl")) == 72
    assert len(read_jsonl_records(root / "aggregates.jsonl")) == 38
    report_index = read_jsonl_records(root / "report_index.jsonl")
    assert len(report_index) == 6
    assert all(item["cases"] for item in report_index)

    raw_records = read_jsonl_records(root / "raw.jsonl")
    assert all(item["metadata"].get("model_signature") for item in raw_records)
    assert all(item["metadata"].get("benchmark_signature") for item in raw_records)
    assert all(item["metadata"].get("execution_signature") for item in raw_records)

    events = read_jsonl_records(root / "events.jsonl")
    event_types = {item.get("event_type") for item in events}
    assert {
        "run.started",
        "model.prepare.started",
        "model.prepare.completed",
        "capability.started",
        "case.started",
        "request.built",
        "inference.started",
        "inference.completed",
        "evaluation.started",
        "evaluation.completed",
        "case.completed",
        "capability.completed",
        "model.release.started",
        "model.release.completed",
        "capability.aggregated",
        "run.completed",
    }.issubset(event_types)
    assert first.metadata["signatures"]["models"]
    assert first.metadata["signatures"]["benchmarks"]
    assert first.metadata["signatures"]["executions"]
    execution_metadata = first.metadata["signatures"]["execution_metadata"]
    assert execution_metadata["qwen3.5-2b-q4km"]["runtime_source"] == "fixture"
    assert execution_metadata["qwen3.5-2b-q4km"]["runtime_key"] == "qwen3.5-2b-q4km"

    resumed_runtime = _FakeRuntime()
    resumed = _runner(tmp_path, runtime=resumed_runtime).run(config)

    assert resumed.planned_cases == 72
    assert resumed.completed_cases == 0
    assert resumed.failed_cases == 0
    assert resumed.skipped_cases == 72
    assert resumed.aggregate_count == 38
    assert len(read_jsonl_records(root / "raw.jsonl")) == 72
    assert len(read_jsonl_records(root / "evaluation.jsonl")) == 72
    assert len(read_jsonl_records(root / "report_index.jsonl")) == 12


def test_retry_failures_reruns_only_failed_cases(tmp_path: Path) -> None:
    failing = _FakeRuntime(fail_sample_ids={"math2-arith-01"})
    config = RunnerConfig(
        run_group="retry-run",
        profile="core",
        model_keys=("qwen3.5-2b-q4km",),
        capability_ids=("mathematical-reasoning",),
        seed=42,
    )

    first = _runner(tmp_path, runtime=failing).run(config)

    assert first.planned_cases == 40
    assert first.completed_cases == 39
    assert first.failed_cases == 1
    assert first.skipped_cases == 0

    no_retry = _runner(tmp_path, runtime=_FakeRuntime()).run(config)
    assert no_retry.completed_cases == 0
    assert no_retry.failed_cases == 0
    assert no_retry.skipped_cases == 40

    retry_config = RunnerConfig(
        run_group=config.run_group,
        profile=config.profile,
        model_keys=config.model_keys,
        capability_ids=config.capability_ids,
        seed=config.seed,
        retry_failures=True,
    )
    retried = _runner(tmp_path, runtime=_FakeRuntime()).run(retry_config)

    assert retried.completed_cases == 1
    assert retried.failed_cases == 0
    assert retried.skipped_cases == 39

    states = read_jsonl_records(tmp_path / "evidence" / "state.jsonl")
    failed = [
        state
        for state in states
        if state.get("status") == "failed"
        and state.get("metadata", {}).get("sample_id") == "math2-arith-01"
    ]
    completed = [
        state
        for state in states
        if state.get("status") == "completed"
        and state.get("metadata", {}).get("sample_id") == "math2-arith-01"
    ]
    assert len(failed) == 1
    assert len(completed) == 1
    assert completed[0]["attempt"] == 2


def test_invalid_inference_is_evaluated_not_recorded_as_pipeline_failure(
    tmp_path: Path,
) -> None:
    class _InvalidProvider(_FakeProvider):
        def generate(self, request: InferenceRequest) -> InferenceResult:
            return InferenceResult(
                provider_id="fake",
                model_id=self.model_id,
                raw_output={"answer": None},
                normalized_output=None,
                latency_ms=1.0,
                valid=False,
                error=InferenceError(
                    kind="invalid_response",
                    message="invalid fixture response",
                ),
            )

    class _InvalidRuntime(_FakeRuntime):
        def prepare(self, model: ResolvedModel) -> _InvalidProvider:
            return _InvalidProvider(model.effective_model_id)

    config = RunnerConfig(
        run_group="invalid-run",
        profile="smoke",
        model_keys=("qwen3.5-2b-q4km",),
        capability_ids=("mathematical-reasoning",),
    )
    summary = _runner(tmp_path, runtime=_InvalidRuntime()).run(config)

    assert summary.completed_cases == 12
    assert summary.failed_cases == 0

    raw = read_jsonl_records(tmp_path / "evidence" / "raw.jsonl")
    evaluations = read_jsonl_records(
        tmp_path / "evidence" / "evaluation.jsonl"
    )
    assert all(item["record"]["valid"] is False for item in raw)
    assert all(item["record"]["valid"] is False for item in evaluations)


def test_unified_runner_enriches_missing_api_cost_from_snapshot(
    tmp_path: Path,
) -> None:
    class _NoCostProvider(_FakeProvider):
        def generate(self, request: InferenceRequest) -> InferenceResult:
            result = super().generate(request)
            return dataclasses.replace(result, estimated_cost_usd=None)

    class _NoCostRuntime(_FakeRuntime):
        def prepare(self, model: ResolvedModel) -> _NoCostProvider:
            self.prepare_calls.append(model.model.model_key)
            return _NoCostProvider(model.effective_model_id)

    config = RunnerConfig(
        run_group="pricing-run",
        profile="smoke",
        model_keys=("gpt-5.6-luna",),
        capability_ids=("structured-output",),
        seed=42,
    )
    summary = _runner(tmp_path, runtime=_NoCostRuntime()).run(config)

    assert summary.completed_cases == 12
    raw = read_jsonl_records(tmp_path / "evidence" / "raw.jsonl")
    assert raw
    assert all(item["record"]["estimated_cost_usd"] is not None for item in raw)
    assert all(
        item["record"]["metadata"]["pricing"]["as_of"] == "2026-09-20"
        for item in raw
    )
