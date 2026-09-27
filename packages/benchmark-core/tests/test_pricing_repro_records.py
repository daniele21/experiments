from __future__ import annotations

from benchmark_core import (
    AggregateMetricRecord,
    EvaluationRecord,
    InferenceError,
    InferenceResult,
    MetricResult,
    RawInferenceRecord,
    TaskResult,
    TokenPrices,
    TokenUsage,
    estimate_token_cost_usd,
    fingerprint_values,
    seeded_random,
)


def test_token_cost_supports_cached_input() -> None:
    cost = estimate_token_cost_usd(
        TokenPrices(
            input_per_million=0.20,
            cached_input_per_million=0.02,
            output_per_million=1.20,
        ),
        input_tokens=1_000_000,
        cached_input_tokens=500_000,
        output_tokens=100_000,
    )

    assert cost == 0.23


def test_seeded_random_matches_python_random_semantics() -> None:
    first = list(range(12))
    second = list(range(12))

    seeded_random(42).shuffle(first)
    seeded_random(42).shuffle(second)

    assert first == second
    assert fingerprint_values(first) == fingerprint_values(second)
    assert fingerprint_values(first) != fingerprint_values(list(reversed(first)))


def test_raw_inference_record_preserves_typed_failure_evidence() -> None:
    result = InferenceResult(
        provider_id="provider",
        model_id="model",
        raw_output={"raw": True},
        normalized_output=None,
        latency_ms=12.0,
        usage=TokenUsage(input_tokens=10, output_tokens=2),
        valid=False,
        error=InferenceError(kind="timeout", message="timed out", retryable=True),
    )

    record = RawInferenceRecord.from_inference_result(
        run_id="run-1",
        run_group="group-1",
        suite_id="suite",
        task_id="routing",
        sample_id="sample-1",
        result=result,
    )

    assert record.valid is False
    assert record.error_kind == "timeout"
    assert record.error_message == "timed out"
    assert record.input_tokens == 10
    assert record.output_tokens == 2


def test_evaluation_and_aggregate_records_are_task_level() -> None:
    task_result = TaskResult(
        task_id="routing",
        sample_id="sample-1",
        prediction="billing",
        expected="billing",
        metrics=(MetricResult(name="accuracy", value=1.0, primary=True),),
    )
    evaluation = EvaluationRecord.from_task_result(
        run_id="run-1",
        evaluator_version="1",
        result=task_result,
    )
    aggregate = AggregateMetricRecord(
        model_key="model-a",
        task_id="routing",
        metric="accuracy",
        value=1.0,
        sample_count=1,
    )

    assert evaluation.metrics[0].name == "accuracy"
    assert aggregate.sample_count == 1
    assert aggregate.failure_count == 0
