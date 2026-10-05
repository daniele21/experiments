from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from benchmark_core import (
    DatasetLoadContext,
    InferenceResult,
    Sample,
    TaskExecutionContext,
    load_dataset_profiles,
)

from model_capability_bench import (
    build_dataset_registry,
    build_task_registry,
    load_capability_suite,
)
from model_capability_bench.datasets.selection import select_samples
from model_capability_bench.runner.capability_data import load_capability_datasets

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets.yaml"
PROFILES = ROOT / "profiles.yaml"
TASKS = ROOT / "tasks.yaml"


def _write_public_fixtures(cache_dir: Path) -> None:
    banking = cache_dir / "banking77"
    banking.mkdir(parents=True, exist_ok=True)
    (banking / "categories.json").write_text(
        json.dumps(["cash_withdrawal", "card_payment", "refund"]),
        encoding="utf-8",
    )
    (banking / "test.csv").write_text(
        "text,category\n"
        "Cash withdrawal one,cash_withdrawal\n"
        "Cash withdrawal two,cash_withdrawal\n"
        "Card payment one,card_payment\n"
        "Card payment two,card_payment\n"
        "Refund one,refund\n"
        "Refund two,refund\n",
        encoding="utf-8",
    )

    clinc = cache_dir / "clinc150"
    clinc.mkdir(parents=True, exist_ok=True)
    (clinc / "data_full.json").write_text(
        json.dumps(
            {
                "oos_test": [
                    ["What is the weather tomorrow?", "weather"],
                    ["Play some jazz music", "music"],
                    ["My bank card is blocked", "banking_overlap"],
                    ["How tall is Mount Everest?", "factoid"],
                    ["Book a restaurant table", "restaurant"],
                ]
            }
        ),
        encoding="utf-8",
    )


def test_catalog_profiles_and_task_references_are_consistent() -> None:
    datasets = build_dataset_registry(DATASETS)
    tasks = build_task_registry(TASKS)
    profiles = load_dataset_profiles(PROFILES)

    assert datasets.summary() == {
        "datasets": 8,
        "dataset_ids": [
            "banking77",
            "clinc150-oos",
            "math-reasoning-controlled-v1",
            "math-reasoning-controlled-v2",
            "qa-abstention-controlled-v1",
            "qa-abstention-controlled-v2",
            "structured-output-controlled-v1",
            "structured-output-controlled-v2",
        ],
        "adapters": [
            "banking77",
            "clinc150-oos",
            "controlled-yaml",
            "structured-output-controlled",
        ],
    }
    assert set(profiles) == {
        "smoke",
        "core",
        "extended",
        "budget",
        "standard",
        "full",
    }

    for task in tasks.select():
        for dataset_id in task.spec.compatible_datasets:
            assert dataset_id in datasets.datasets


def test_banking77_adapter_is_balanced_and_reproducible(tmp_path: Path) -> None:
    _write_public_fixtures(tmp_path)
    registry = build_dataset_registry(DATASETS)
    profile = load_dataset_profiles(PROFILES)["smoke"]
    context = DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42)

    first = registry.load("banking77", context)
    second = registry.load("banking77", context)

    assert first.available_count == 6
    assert len(first.samples) == 6
    assert first.selection_fingerprint == second.selection_fingerprint
    assert [sample.sample_id for sample in first.samples] == [
        sample.sample_id for sample in second.samples
    ]
    assert {sample.expected for sample in first.samples} == {
        "cash_withdrawal",
        "card_payment",
        "refund",
    }
    assert all(
        sample.metadata["labels"]
        == ("cash_withdrawal", "card_payment", "refund")
        for sample in first.samples
    )
    assert set(first.source_checksums) == {"test", "categories"}


def test_clinc150_adapter_filters_configured_finance_overlap(tmp_path: Path) -> None:
    _write_public_fixtures(tmp_path)
    registry = build_dataset_registry(DATASETS)
    profile = load_dataset_profiles(PROFILES)["full"]
    context = DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=7)

    loaded = registry.load("clinc150-oos", context)

    assert loaded.available_count == 4
    assert len(loaded.samples) == 4
    assert all(sample.expected == "other" for sample in loaded.samples)
    assert all("bank card" not in str(sample.input).lower() for sample in loaded.samples)
    assert loaded.metadata == {
        "upstream_split_count": 5,
        "filtered_count": 4,
        "filter": "exclude_terms",
    }
    assert set(loaded.source_checksums) == {"source"}


def test_controlled_structured_output_dataset_loads_repository_cases(
    tmp_path: Path,
) -> None:
    registry = build_dataset_registry(DATASETS)
    profile = load_dataset_profiles(PROFILES)["full"]
    loaded = registry.load(
        "structured-output-controlled-v1",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )

    assert loaded.available_count == 12
    assert len(loaded.samples) == 12
    assert loaded.samples[0].sample_id == "invoice-basic"
    assert isinstance(loaded.samples[0].metadata["response_schema"], dict)
    assert loaded.metadata["repository_path"] == (
        "data/structured-output-controlled-v1.yaml"
    )
    assert set(loaded.source_checksums) == {"repository_file"}


def test_profiles_are_configuration_driven() -> None:
    profiles = load_dataset_profiles(PROFILES)

    assert profiles["smoke"].max_cases_for("banking77") == 77
    assert profiles["budget"].max_cases_for("banking77") == 154
    assert profiles["standard"].max_cases_for("clinc150-oos") == 500
    assert profiles["core"].max_cases_for("banking77") == 154
    assert profiles["core"].max_cases_for("structured-output-controlled-v2") == 60
    assert profiles["extended"].max_cases_for("banking77") == 770
    assert profiles["full"].max_cases_for("banking77") is None
    assert (
        profiles["smoke"].max_cases_for("structured-output-controlled-v1")
        is None
    )
    assert profiles["budget"].max_cases_for("qa-abstention-controlled-v1") is None
    assert (
        profiles["standard"].max_cases_for("math-reasoning-controlled-v1")
        is None
    )


def test_public_dataset_catalog_uses_pinned_revisions_and_no_moving_main() -> None:
    text = DATASETS.read_text(encoding="utf-8")
    registry = build_dataset_registry(DATASETS)

    assert registry.get("banking77").spec.revision == (
        "9d081458ff52e53cf7e848f414e6e9344e4e6696"
    )
    assert registry.get("clinc150-oos").spec.revision == (
        "48a0e1cff8f43dd4d0836ecb4ed5df08733e3d2e"
    )
    assert "/main/" not in text
    assert "refs/heads/main" not in text


def test_v2_controlled_datasets_have_vertical_family_coverage(tmp_path: Path) -> None:
    registry = build_dataset_registry(DATASETS)
    profile = load_dataset_profiles(PROFILES)["core"]

    structured = registry.load(
        "structured-output-controlled-v2",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )
    qa = registry.load(
        "qa-abstention-controlled-v2",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )
    reasoning = registry.load(
        "math-reasoning-controlled-v2",
        DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
    )

    assert len(structured.samples) == 60
    assert len(qa.samples) == 60
    assert len(reasoning.samples) == 40
    assert {sample.metadata["family"] for sample in structured.samples} == {
        "flat", "nested", "arrays", "optional", "noisy", "adversarial"
    }
    assert {sample.metadata["family"] for sample in qa.samples} == {
        "direct", "distractor", "missing", "near_answer", "contradiction", "multi_hop"
    }
    assert {sample.metadata["family"] for sample in reasoning.samples} == {
        "arithmetic", "percentages", "multi_step", "algebra", "logic", "constraints"
    }
    assert all(sample.metadata.get("difficulty") for sample in structured.samples)


def test_smoke_capability_selection_is_actually_stratified(tmp_path: Path) -> None:
    bundle = load_capability_suite(ROOT)
    profile = bundle.profiles["smoke"]
    cache = {}

    expected_families = {
        "structured-output": {
            "flat", "nested", "arrays", "optional", "noisy", "adversarial"
        },
        "qa-abstention": {
            "direct", "distractor", "missing", "near_answer", "contradiction", "multi_hop"
        },
        "mathematical-reasoning": {
            "arithmetic", "percentages", "multi_step", "algebra", "logic", "constraints"
        },
    }

    for capability_id, families in expected_families.items():
        capability = next(
            item
            for item in bundle.resolved_capabilities
            if item.spec.capability_id == capability_id
        )
        loaded = load_capability_datasets(
            suite=bundle,
            capability=capability,
            profile=profile,
            profile_id="smoke",
            cache_dir=tmp_path,
            seed=42,
            cache=cache,
        )
        samples = [
            sample
            for dataset in loaded.values()
            for sample in dataset.samples
        ]
        counts = Counter(sample.metadata["family"] for sample in samples)
        assert len(samples) == 12
        assert set(counts) == families
        assert set(counts.values()) == {2}


def test_v2_gold_outputs_self_score_perfectly(tmp_path: Path) -> None:
    bundle = load_capability_suite(ROOT)
    profile = bundle.profiles["core"]

    cases = [
        (
            "structured-output",
            "structured-output-controlled-v2",
            lambda sample: sample.expected,
            "exact_match",
        ),
        (
            "qa-abstention",
            "qa-abstention-controlled-v2",
            lambda sample: {
                "answer": sample.expected["answer"] if sample.expected["answerable"] else "",
                "abstain": not sample.expected["answerable"],
            },
            "qa_correct",
        ),
        (
            "mathematical-reasoning",
            "math-reasoning-controlled-v2",
            lambda sample: {"answer": str(sample.expected)},
            "final_answer_accuracy",
        ),
    ]

    for task_id, dataset_id, prediction_for, primary_metric in cases:
        loaded = bundle.datasets.load(
            dataset_id,
            DatasetLoadContext(cache_dir=tmp_path, profile=profile, seed=42),
        )
        task = bundle.tasks.get(task_id)
        context = TaskExecutionContext(
            run_id="gold-self-check",
            dataset_id=dataset_id,
            profile="core",
            generation=bundle.suite.generation,
        )
        for sample in loaded.samples:
            prediction = prediction_for(sample)
            result = task.evaluate(
                sample,
                InferenceResult(
                    provider_id="gold",
                    model_id="gold",
                    raw_output=prediction,
                    normalized_output=prediction,
                    latency_ms=0.0,
                ),
                context,
            )
            metrics = {metric.name: metric.value for metric in result.metrics}
            assert result.valid is True, sample.sample_id
            assert metrics[primary_metric] == 1.0, sample.sample_id


def test_stratified_selection_validates_quotas_even_when_selecting_all(
    tmp_path: Path,
) -> None:
    profile = load_dataset_profiles(PROFILES)["full"]
    context = DatasetLoadContext(
        cache_dir=tmp_path,
        profile=profile,
        seed=42,
        max_cases_override=None,
        max_cases_override_enabled=True,
        selection={
            "strategy": "stratified",
            "quotas": [{"match": {"family": "missing"}, "count": 1}],
        },
    )

    with pytest.raises(ValueError, match="only 0 are available"):
        select_samples(
            (
                Sample(
                    sample_id="a",
                    input="A",
                    metadata={"family": "present"},
                ),
            ),
            dataset_id="fixture",
            context=context,
        )
