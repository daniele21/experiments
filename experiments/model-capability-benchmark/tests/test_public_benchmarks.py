from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from benchmark_core import (
    InferenceResult,
    TaskExecutionContext,
)

from model_capability_bench import build_dataset_registry, load_capability_suite
from model_capability_bench.datasets import public_benchmarks
from model_capability_bench.runner.capability_data import load_capability_datasets

ROOT = Path(__file__).resolve().parents[1]


def _fixture_spec(dataset_id: str):
    return build_dataset_registry(ROOT / "datasets.yaml").get(dataset_id).spec


def test_opt_in_suite_does_not_change_legacy_core() -> None:
    old = load_capability_suite(ROOT)
    assert old.suite.suite_id == "capability-core"
    assert len(old.resolved_capabilities) == 5

    public = load_capability_suite(ROOT, suite_filename="suite_public.yaml")
    assert public.suite.suite_id == "capability-public-benchmarks"
    assert len(public.resolved_capabilities) == 3
    assert public.suite_filename == "suite_public.yaml"
    assert {c.spec.capability_id for c in public.resolved_capabilities} == {
        "public-mathematical-reasoning",
        "public-qa-abstention",
        "public-json-schema-compliance",
    }


def test_gsm8k_gold_final_answers_are_numeric_and_source_rows_preserved() -> None:
    adapter = public_benchmarks.PublicParquetBenchmark(_fixture_spec("gsm8k-main-test"))
    rows = [
        {"question": "If a pack costs $1, how much do 1,200 packs cost?",
         "answer": "Compute the total.\n#### 1,200"},
        {"question": "Find the remaining balance.",
         "answer": "Subtract amounts.\n#### 3.50"},
    ]
    samples, stats = adapter._convert(rows)
    assert [case.expected for case in samples] == ["1200", "3.5"]
    assert [case.metadata["source_index"] for case in samples] == [0, 1]
    assert len({case.sample_id for case in samples}) == 2
    assert stats == {"source_rows": 2, "excluded_rows": 0}


def test_squad_gold_aliases_and_abstention_preserved() -> None:
    adapter = public_benchmarks.PublicParquetBenchmark(
        _fixture_spec("squad-v2-validation")
    )
    rows = [
        {"id": "abc1", "title": "Example", "context": "The answer is the 10th century.",
         "question": "When?", "answers": {
             "text": ["the 10th century", "10th century"],
             "answer_start": [14, 18],
         }},
        {"id": "abc2", "title": "Example", "context": "It does not say.",
         "question": "When?", "answers": {"text": [], "answer_start": []}},
    ]
    samples, _ = adapter._convert(rows)
    assert samples[0].metadata["accepted_answers"] == [
        "the 10th century", "10th century"
    ]
    assert samples[1].expected == {"answer": "", "answerable": False}

    suite = load_capability_suite(ROOT, suite_filename="suite_public.yaml")
    task = suite.tasks.get("qa-abstention")
    context = TaskExecutionContext(
        run_id="public-test", dataset_id="squad-v2-validation",
        profile="core", generation=suite.suite.generation,
    )
    correct = task.evaluate(
        samples[0],
        InferenceResult(
            provider_id="test", model_id="test",
            raw_output={"answer": "10th century", "abstain": False},
            normalized_output={"answer": "10th century", "abstain": False},
            latency_ms=0.0,
        ),
        context,
    )
    assert next(m.value for m in correct.metrics if m.name == "qa_correct") == 1.0

    abstained = task.evaluate(
        samples[1],
        InferenceResult(
            provider_id="test", model_id="test",
            raw_output={"answer": "", "abstain": True},
            normalized_output={"answer": "", "abstain": True},
            latency_ms=0.0,
        ),
        context,
    )
    assert next(m.value for m in abstained.metrics if m.name == "qa_correct") == 1.0


def test_squad_core_selects_balanced_answerability_without_network(
    monkeypatch, tmp_path: Path
) -> None:
    rows = [
        {"id": f"{n:05d}", "title": "Fixture",
         "context": f"Person {n} lives in Rome.",
         "question": f"Where does person {n} live?",
         "answers": {
             "text": ["Rome"] if n % 2 else [],
             "answer_start": [18] if n % 2 else [],
         }}
        for n in range(160)
    ]
    path = tmp_path / "fixture.parquet"
    path.write_bytes(b"test-only data")
    monkeypatch.setattr(public_benchmarks, "single_cached_source", lambda *_: path)
    monkeypatch.setattr(public_benchmarks, "_rows", lambda *_: rows)
    bundle = load_capability_suite(ROOT, suite_filename="suite_public.yaml")
    capability = next(
        c for c in bundle.resolved_capabilities
        if c.spec.capability_id == "public-qa-abstention"
    )
    kwargs = {
        "suite": bundle, "capability": capability,
        "profile": bundle.profiles["core"], "profile_id": "core",
        "cache_dir": tmp_path, "seed": 42,
    }
    a = load_capability_datasets(**kwargs, cache={})["squad-v2-validation"]
    b = load_capability_datasets(**kwargs, cache={})["squad-v2-validation"]
    assert len(a.samples) == 60
    assert a.selection_fingerprint == b.selection_fingerprint
    assert Counter(c.metadata["answerable"] for c in a.samples) == {
        True: 30, False: 30
    }
    assert set(a.source_checksums) == {"source"}


def test_jsonschemabench_only_scores_schema_compliance() -> None:
    adapter = public_benchmarks.PublicParquetBenchmark(
        _fixture_spec("jsonschemabench-github-easy-test")
    )
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer", "minimum": 2}},
        "required": ["count"], "additionalProperties": False,
    }
    remote = {"type": "object", "properties": {
        "external": {"$ref": "https://example.org/anything"}
    }}
    cases, stats = adapter._convert([
        {"unique_id": "ok", "json_schema": json.dumps(schema)},
        {"unique_id": "remote", "json_schema": json.dumps(remote)},
    ])
    assert len(cases) == 1
    assert stats["excluded_rows"] == 1
    assert cases[0].expected is None

    suite = load_capability_suite(ROOT, suite_filename="suite_public.yaml")
    task = suite.tasks.get("json-schema-compliance")
    ctx = TaskExecutionContext(
        run_id="public-test", dataset_id="jsonschemabench-github-easy-test",
        profile="core", generation=suite.suite.generation,
    )

    def score(value):
        result = task.evaluate(
            cases[0],
            InferenceResult(provider_id="test", model_id="test",
                            raw_output=value, normalized_output=value,
                            latency_ms=0.0),
            ctx,
        )
        return next(m.value for m in result.metrics
                    if m.name == "schema_valid_rate")

    assert score({"count": 3}) == 1.0
    assert score({"count": 1}) == 0.0
    assert score({"count": "3"}) == 0.0


def test_public_suite_path_is_restricted() -> None:
    import pytest

    with pytest.raises(ValueError, match="YAML basename"):
        load_capability_suite(ROOT, suite_filename="../other.yaml")
