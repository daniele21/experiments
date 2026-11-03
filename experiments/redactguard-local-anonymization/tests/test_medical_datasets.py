"""Offline adapter tests. Do not download or bundle upstream medical corpora in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from redact_bench.datasets import load_dataset
from redact_bench.medical_datasets import (
    _asq_entities, _meddocan_entities, _pharmaer_entities,
    prepare_asq, prepare_meddocan, prepare_pharmaer,
)
from redact_bench.suite import load_suite_config

ROOT = Path(__file__).resolve().parents[1]


def _asq_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "asq.txt"
    source.write_text(
        '===QUERY===\nPatient Anna has MS and takes metformin.\n'
        '===PHI_TAGS===\n{"identifier_type":"NAME","value":"Anna"}\n\n'
        '===QUERY===\nGuidelines for metformin in diabetes at age 50.\n'
        '===PHI_TAGS===\n\n'
        '===QUERY===\nPatient with MRN 12345 visited on March 3, 2025.\n'
        '===PHI_TAGS===\n'
        '{"identifier_type":"MEDICAL_RECORD_NUMBER","value":"12345"}\n'
        '{"identifier_type":"DATE","value":"March 3, 2025"}\n',
        encoding="utf-8",
    )
    return source


def test_asq_import_preserves_gold_categories_and_uses_real_negatives(tmp_path: Path):
    source = _asq_fixture(tmp_path)
    dest = tmp_path / "asq"
    manifest = prepare_asq(source, dest, positives=2, negatives=1, strict_size=False)
    cases = load_dataset(dest / "cases.jsonl")
    assert manifest["cases"] == 3
    assert manifest["gold_count"] == 3
    assert len([case for case in cases if not case.gold]) == 1
    assert {span.pii_type for case in cases for span in case.gold} == {
        "name", "medical_record_number", "date",
    }
    for case in cases:
        for gold in case.gold:
            assert case.text[gold.start:gold.end] == gold.value
        assert case.profile == "asq_phi" and case.gold_scope == "complete"
    neg = next(case for case in cases if not case.gold)
    assert "metformin" in neg.text and "diabetes" in neg.text


def test_asq_ambiguous_value_fail_closed():
    with pytest.raises(ValueError, match="unique/complete"):
        _asq_entities("Anna saw Anna yesterday", [{"identifier_type": "NAME", "value": "Anna"}])
    with pytest.raises(ValueError, match="Overlapping"):
        _asq_entities("Anna Rossi", [
            {"identifier_type": "NAME", "value": "Anna Rossi"},
            {"identifier_type": "NAME", "value": "Anna"},
        ])


def test_asq_rejects_malformed_tags_and_empty_selection(tmp_path: Path):
    source = _asq_fixture(tmp_path)
    with pytest.raises(ValueError, match="at least one"):
        prepare_asq(source, tmp_path / "out", positives=0, negatives=0, strict_size=False)
    source.write_text(
        '===QUERY===\nA\n===PHI_TAGS===\n{"identifier_type":"UNLISTED","value":"A"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown ASQ"):
        prepare_asq(source, tmp_path / "out", positives=1, negatives=0, strict_size=False)


def test_meddocan_brat_preserves_offsets_and_subtypes(tmp_path: Path):
    text = "Paciente Ana fue vista en Hospital Central el 01/05/2020."
    start = text.index("Ana")
    hospital = text.index("Hospital Central")
    ann = (
        f"T1\tNOMBRE_SUJETO_ASISTENCIA {start} {start + 3}\tAna\n"
        f"T2\tHOSPITAL {hospital} {hospital + 16}\tHospital Central\n"
    )
    source = tmp_path / "source" / "corpus" / "test"
    source.mkdir(parents=True)
    (source / "case1.txt").write_text(text, encoding="utf-8")
    (source / "case1.ann").write_text(ann, encoding="utf-8")
    out = tmp_path / "out"
    manifest = prepare_meddocan(tmp_path / "source", out, limit=1)
    cases = load_dataset(out / "cases.jsonl")
    assert len(cases) == 1 and manifest["gold_count"] == 2
    assert [(s.value, s.pii_type) for s in cases[0].gold] == [
        ("Ana", "med_name"), ("Hospital Central", "med_location"),
    ]


def test_meddocan_invalid_offset_and_unmapped_label_refused():
    with pytest.raises(ValueError, match="offsets"):
        _meddocan_entities("Ana", "T1\tNOMBRE_SUJETO_ASISTENCIA 1 3\tAna")
    with pytest.raises(ValueError, match="Unmapped"):
        _meddocan_entities("Ana", "T1\tUNEXPECTED 0 3\tAna")


def _pharma_fixture() -> dict:
    return {
        "document_id": "aifa-1",
        "text": "Metformina per il diabete.",
        "tokens": ["Metformina", "per", "il", "diabete", "."],
        "start_end": [[0, 10], [11, 14], [15, 17], [18, 25], [25, 26]],
        "labels": ["B-DRUG", "O", "O", "B-DISEASE", "O"],
    }


def test_pharmaer_bio_exact_gold_and_separate_profile(tmp_path: Path):
    source = tmp_path / "test.jsonl"
    source.write_text(json.dumps(_pharma_fixture()) + "\n", encoding="utf-8")
    manifest = prepare_pharmaer(source, tmp_path / "out", strict_test_size=False)
    case = load_dataset(tmp_path / "out" / "cases.jsonl")[0]
    assert manifest["task"] == "clinical_entity_recognition_not_deidentification"
    assert [(s.pii_type, s.value) for s in case.gold] == [
        ("clinical_drug", "Metformina"), ("clinical_disease", "diabete"),
    ]
    assert case.profile == "clinical_ner"
    assert "not_pii" in case.tags


def test_pharmaer_bad_offsets_and_orphan_bio_refused():
    row = _pharma_fixture()
    row["start_end"][0] = [1, 10]
    with pytest.raises(ValueError, match="offsets"):
        _pharmaer_entities(row)
    row = _pharma_fixture()
    row["labels"][0] = "I-DRUG"
    with pytest.raises(ValueError, match="Orphan"):
        _pharmaer_entities(row)


def test_medical_configs_have_distinct_profiles_and_gold_versions():
    config = yaml.safe_load((ROOT / "config/profiles-medical-gold.yaml").read_text())
    assert set(config["profiles"]["asq_phi"]) == {
        "name", "geographic_location", "date", "medical_record_number",
        "health_plan_beneficiary_number", "phone_number", "social_security_number",
        "email_address", "unique_identifier", "account_number", "fax_number",
        "certificate_license_number", "ip_address",
    }
    assert set(config["profiles"]["clinical_ner"]) == {
        "clinical_drug", "clinical_disease", "clinical_symptom", "clinical_anatomical_part",
    }
    for name in ("asq-phi", "meddocan", "pharmaer"):
        suite = load_suite_config(ROOT / "config" / f"suite-{name}.yaml", root=ROOT)
        assert suite.profiles.name == "profiles-medical-gold.yaml"
        assert suite.dataset.name == "cases.jsonl"
        assert suite.quality_only and suite.inference_cache_max_entries == 0
