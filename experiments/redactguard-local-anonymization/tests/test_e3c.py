"""Offline E3C contract tests: never download clinical narratives in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from redact_bench.datasets import load_dataset
from redact_bench.e3c import GOLD_VERSION, prepare_e3c
from redact_bench.metrics import aggregate_detailed, score_case
from redact_bench.models import Case, Finding, InferenceResult, Span


def _fixture_source(root: Path) -> Path:
    docs = root / "data_collection/Italian/layer1"
    annotations = root / "data_annotation/Italian/layer1"
    documentation = root / "documentation"
    for folder in (docs, annotations, documentation):
        folder.mkdir(parents=True)
    ids = [f"IT{100000 + i:06d}" for i in range(86)]
    (documentation / "train_test_split.txt").write_text(
        "BASQUE\n'EU100001'\n\nITALIAN\n"
        + ", ".join(repr(i) for i in ids[:36])
        + "\n\nSPANISH\n'ES100001'\n",
        encoding="utf-8",
    )
    for source_id in ids:
        (docs / f"{source_id}.json").write_text(
            json.dumps({
                "id": source_id,
                "language": "it",
                "text": "Anna presenta ipertensione arteriosa e assume metformina. "
                "La paziente ha 47 anni e il controllo è stabile.",
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (annotations / f"{source_id}.xml").write_text(
            "<cas/>", encoding="utf-8"
        )
    return root


def test_e3c_official_split_and_targeted_gold_are_deterministic(tmp_path: Path):
    source = _fixture_source(tmp_path / "source")
    output = tmp_path / "data" / "cache" / "e3c"
    first = prepare_e3c(source, output, verify_checkout=False)
    cases = load_dataset(output / "synthetic_pii.jsonl")
    assert len(cases) == 50
    assert {case.profile for case in cases} == {"healthcare"}
    assert {case.gold_version for case in cases} == {GOLD_VERSION}
    assert {case.gold_scope for case in cases} == {"injected_only"}
    assert all(len(case.gold) == 6 for case in cases)
    assert all(case.human_reviewed is False for case in cases)
    assert all(
        case.text[span.start:span.end] == span.value
        for case in cases for span in case.gold
    )
    assert {case.content_family_id for case in cases} == {
        f"e3c-it-IT{100000 + n:06d}" for n in range(36, 86)
    }
    assert "Anna presenta ipertensione" in cases[0].text
    initial_bytes = (output / "synthetic_pii.jsonl").read_bytes()
    second = prepare_e3c(source, output, verify_checkout=False)
    assert (output / "synthetic_pii.jsonl").read_bytes() == initial_bytes
    assert first == second
    assert first["official_test_documents"] == 50
    assert first["synthetic_pii"]["scoring"] == "targeted_recall_and_leakage_only"
    assert len(first["test_sources"]) == 50


def test_e3c_original_context_cannot_be_misranked_as_zero_pii(tmp_path: Path):
    source = _fixture_source(tmp_path / "source")
    out = tmp_path / "cache"
    prepare_e3c(source, out, verify_checkout=False)
    with pytest.raises(ValueError, match="unscorable gold_scope"):
        load_dataset(out / "clinical_context.jsonl")


def test_e3c_incomplete_annotations_do_not_create_false_precision(tmp_path: Path):
    source = _fixture_source(tmp_path / "source")
    out = tmp_path / "cache"
    prepare_e3c(source, out, verify_checkout=False)
    case = load_dataset(out / "synthetic_pii.jsonl")[0]
    synthetic = case.gold[0]
    clinical_value = "ipertensione"
    clinical_start = case.text.index(clinical_value)
    result = InferenceResult(
        case_id=case.case_id, model="fixture", valid=True, latency_ms=10,
        findings=[
            Finding(
                pii_type=synthetic.pii_type, value=synthetic.value,
                start=synthetic.start, end=synthetic.end,
            ),
            Finding(
                pii_type="health_condition", value=clinical_value,
                start=clinical_start, end=clinical_start + len(clinical_value),
            ),
        ],
        raw_content="{}", raw_item_count=2, resolved_item_count=2,
    )
    row = score_case(case, result)
    assert row["pii_recall"] == pytest.approx(1 / 6)
    assert row["precision"] is None
    assert row["span_f1"] is None
    assert row["over_redaction_rate"] is None
    assert row["fp"] == 0
    assert row["unscored_prediction_count"] == 1
    assert row["false_positives"] == []
    summary = aggregate_detailed([row])
    assert summary["micro"]["precision"] is None
    assert summary["micro"]["over_redaction_rate"] is None
    assert summary["macro"]["precision"] is None
    assert all(t["precision"] is None for t in summary["by_type"].values())
    assert summary["micro"]["gold_scope"] == "injected_only"


def test_complete_gold_is_unchanged_and_mixed_scopes_refused():
    case = Case(
        case_id="complete", profile="general", text="Mario e Paolo",
        gold=(Span(0, 5, "private_person", "Mario"),),
    )
    prediction = InferenceResult(
        case_id="complete", model="fixture", valid=True, latency_ms=1,
        findings=[Finding("private_person", "Paolo", 8, 13)], raw_content="{}",
    )
    scored = score_case(case, prediction)
    assert scored["fp"] == 1
    assert scored["precision"] == 0.0
    partial = score_case(
        Case(
            case_id="partial", profile="general", text=case.text,
            gold=case.gold, gold_scope="injected_only",
        ),
        prediction,
    )
    with pytest.raises(ValueError, match="Cannot aggregate"):
        aggregate_detailed([scored, partial])


def test_incorrect_e3c_split_fails_closed(tmp_path: Path):
    source = _fixture_source(tmp_path / "source")
    (source / "documentation/train_test_split.txt").write_text(
        "ITALIAN\n'IT100001'\nSPANISH\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="36 distinct"):
        prepare_e3c(source, tmp_path / "out", verify_checkout=False)
