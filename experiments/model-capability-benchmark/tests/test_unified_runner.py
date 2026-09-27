from __future__ import annotations

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

    assert first.planned_cases == 64
    assert first.completed_cases == 64
    assert first.failed_cases == 0
    assert first.skipped_cases == 0
    assert first.model_failures == 0
    assert first.aggregate_count == 34
    assert runtime.prepare_calls == ["qwen3.5-2b-q4km", "gpt-5.6-luna"]
    assert runtime.release_calls == runtime.prepare_calls

    root = tmp_path / "evidence"
    assert len(read_jsonl_records(root / "raw.jsonl")) == 64
    assert len(read_jsonl_records(root / "evaluation.jsonl")) == 64
    assert len(read_jsonl_records(root / "report_index.jsonl")) == 12
    assert len(read_jsonl_records(root / "aggregates.jsonl")) == 34
    report_index = read_jsonl_records(root / "report_index.jsonl")
    assert len(report_index) == 6
    assert all(item["cases"] for item in report_index)

    resumed_runtime = _FakeRuntime()
    resumed = _runner(tmp_path, runtime=resumed_runtime).run(config)

    assert resumed.planned_cases == 64
    assert resumed.completed_cases == 0
    assert resumed.failed_cases == 0
    assert resumed.skipped_cases == 64
    assert resumed.aggregate_count == 34
    assert len(read_jsonl_records(root / "raw.jsonl")) == 64
    assert len(read_jsonl_records(root / "evaluation.jsonl")) == 64


def test_retry_failures_reruns_only_failed_cases(tmp_path: Path) -> None:
    failing = _FakeRuntime(fail_sample_ids={"math-003"})
    config = RunnerConfig(
        run_group="retry-run",
        profile="smoke",
        model_keys=("qwen3.5-2b-q4km",),
        capability_ids=("mathematical-reasoning",),
        seed=42,
    )

    first = _runner(tmp_path, runtime=failing).run(config)

    assert first.planned_cases == 10
    assert first.completed_cases == 9
    assert first.failed_cases == 1
    assert first.skipped_cases == 0

    no_retry = _runner(tmp_path, runtime=_FakeRuntime()).run(config)
    assert no_retry.completed_cases == 0
    assert no_retry.failed_cases == 0
    assert no_retry.skipped_cases == 10

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
    assert retried.skipped_cases == 9

    states = read_jsonl_records(tmp_path / "evidence" / "state.jsonl")
    failed = [
        state
        for state in states
        if state.get("status") == "failed"
        and state.get("metadata", {}).get("sample_id") == "math-003"
    ]
    completed = [
        state
        for state in states
        if state.get("status") == "completed"
        and state.get("metadata", {}).get("sample_id") == "math-003"
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

    assert summary.completed_cases == 10
    assert summary.failed_cases == 0

    raw = read_jsonl_records(tmp_path / "evidence" / "raw.jsonl")
    evaluations = read_jsonl_records(
        tmp_path / "evidence" / "evaluation.jsonl"
    )
    assert all(item["record"]["valid"] is False for item in raw)
    assert all(item["record"]["valid"] is False for item in evaluations)
