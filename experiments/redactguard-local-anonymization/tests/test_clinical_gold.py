"""Offline public clinical NER benchmark tests: never fetch external texts in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from redact_bench.clinical_gold import (
    _uima_to_python_offset, e3c_clinical_entities,
    prepare_e3c_clinical, prepare_spaccc,
)
from redact_bench.datasets import load_dataset


def _jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )
    return path


def _spaccc_fixture(tmp_path: Path) -> tuple[Path, Path]:
    docs = [
        {"filename": "es-A.txt", "document": "Paciente con diabetes y fiebre."},
        {"filename": "es-B.txt", "document": "Se realizó una biopsia y se detectó VIH."},
        {"filename": "es-C.txt", "document": "El paciente recibió ibuprofeno."},
        {"filename": "es-D.txt", "document": "Sin enfermedades conocidas."},
    ]
    labels = [
        {"filename": "A", "ann_id": 1, "label": "DISEASE",
         "start_span": 13, "end_span": 21, "text": "diabetes"},
        {"filename": "A", "ann_id": 2, "label": "SYMPTOM",
         "start_span": 24, "end_span": 30, "text": "fiebre"},
        # Duplicate identical annotation should be deduplicated.
        {"filename": "A", "ann_id": 3, "label": "SYMPTOM",
         "start_span": 24, "end_span": 30, "text": "fiebre"},
        {"filename": "B", "ann_id": 4, "label": "PROCEDURE",
         "start_span": 15, "end_span": 22, "text": "biopsia"},
        {"filename": "B", "ann_id": 5, "label": "DISEASE",
         "start_span": 36, "end_span": 39, "text": "VIH"},
        {"filename": "C", "ann_id": 6, "label": "CHEMICAL",
         "start_span": 20, "end_span": 30, "text": "ibuprofeno"},
        {"filename": "D", "ann_id": 7, "label": "DISEASE",
         "start_span": 4, "end_span": 16, "text": "enfermedades"},
    ]
    return _jsonl(tmp_path / "test-fixture.jsonl", labels), _jsonl(
        tmp_path / "train-fixture.jsonl", docs,
    )


def test_spaccc_rejoins_original_documents_and_preserves_source_classes(tmp_path: Path):
    labels, documents = _spaccc_fixture(tmp_path)
    output = tmp_path / "prepared"
    report = prepare_spaccc(labels, documents, output, limit=3)
    cases = load_dataset(output / "cases.jsonl")
    assert report["cases"] == 3
    assert report["test_documents_total"] == 4
    assert len({c.case_id for c in cases}) == 3
    assert {c.profile for c in cases} == {"spaccc_clinical_ner"}
    assert all(c.gold_scope == "complete" for c in cases)
    assert report["gold_version"].startswith("spaccc_es_clinical_gold_v1-")
    for case in cases:
        for span in case.gold:
            assert case.text[span.start:span.end] == span.value
    first_version = report["gold_version"]
    assert first_version == prepare_spaccc(labels, documents, output, limit=3)["gold_version"]
    other_version = prepare_spaccc(labels, documents, output, limit=2)["gold_version"]
    assert other_version != first_version


def test_spaccc_preserves_nested_cross_class_spans(tmp_path: Path):
    labels, documents = _spaccc_fixture(tmp_path)
    rows = [json.loads(line) for line in labels.read_text().splitlines()]
    # Same span with different source labels remains a valid multilabel gold.
    rows.append({"filename": "A", "ann_id": 12, "label": "DISEASE",
                 "start_span": 24, "end_span": 30, "text": "fiebre"})
    _jsonl(labels, rows)
    report = prepare_spaccc(labels, documents, tmp_path / "out", limit=4)
    assert report["cases"] == 4
    assert report["by_label"]["clinical_symptom"] >= 1
    a = next(c for c in load_dataset(tmp_path / "out" / "cases.jsonl")
             if c.case_id.endswith("-A"))
    kinds = {s.pii_type for s in a.gold if s.value == "fiebre"}
    assert kinds == {"clinical_symptom", "clinical_disease"}


def test_spaccc_rejects_leaked_train_annotations_and_missing_alignment(tmp_path: Path):
    labels, documents = _spaccc_fixture(tmp_path)
    with pytest.raises(ValueError, match="test"):
        prepare_spaccc(documents, labels, tmp_path / "out", limit=1)
    rows = [json.loads(line) for line in labels.read_text().splitlines()]
    rows[0]["start_span"] = 0
    _jsonl(labels, rows)
    with pytest.raises(ValueError, match="Only 3 exact-aligned"):
        prepare_spaccc(labels, documents, tmp_path / "out", limit=4)


def test_spaccc_rejects_missing_or_unknown_classes(tmp_path: Path):
    labels, documents = _spaccc_fixture(tmp_path)
    rows = [json.loads(line) for line in labels.read_text().splitlines()]
    rows[0]["label"] = "PRIVATE_DIAGNOSIS_NOT_SOURCE"
    _jsonl(labels, rows)
    with pytest.raises(ValueError, match="need 4"):
        prepare_spaccc(labels, documents, tmp_path / "out", limit=4)


def _e3c_fixture(source: Path) -> Path:
    folders = [
        source / "data_collection/Italian/layer1",
        source / "data_annotation/Italian/layer1",
        source / "documentation",
    ]
    for folder in folders:
        folder.mkdir(parents=True)
    ids = [f"IT{100000+i:06d}" for i in range(86)]
    (source / "documentation/train_test_split.txt").write_text(
        "ITALIAN\n" + ", ".join(repr(s) for s in ids[:36])
        + "\n\nSPANISH\n'ES100001'\n",
        encoding="utf-8",
    )
    narrative = "Paziente con diabete; pressione 130/80."
    xml = (
        '<?xml version="1.0"?><xmi:XMI xmlns:xmi="http://www.omg.org/XMI" '
        'xmlns:cas="http:///uima/cas.ecore" xmlns:custom="http:///webanno/custom.ecore">'
        f'<cas:Sofa sofaString="{narrative}&#13;&#10;"/>'
        '<custom:CLINENTITY begin="13" end="20" entityID="C0011849"/>'
        '<custom:ACTOR begin="0" end="8" role="PATIENT"/>'
        '<custom:RML begin="32" end="38"/>'
        '<custom:EVENT begin="21" end="30"/>'
        '</xmi:XMI>'
    )
    for value in ids:
        (folders[0] / f"{value}.json").write_text(
            json.dumps({"id": value, "language": "it", "text": narrative}),
            encoding="utf-8",
        )
        (folders[1] / f"{value}.xml").write_text(xml, encoding="utf-8")
    return source


def test_e3c_source_gold_xml_uses_exact_offsets_and_ignores_temporal_events(tmp_path: Path):
    source = _e3c_fixture(tmp_path / "e3c")
    output = tmp_path / "clinical"
    manifest = prepare_e3c_clinical(source, output, verify_checkout=False)
    assert manifest["cases"] == 50
    assert manifest["by_label"]["e3c_actor"] == 50
    assert manifest["by_label"]["e3c_clinical_entity"] == 50
    assert manifest["by_label"]["e3c_measurement"] == 50
    assert manifest["gold_spans"] == 150
    cases = load_dataset(output / "cases.jsonl")
    assert {case.profile for case in cases} == {"e3c_clinical_ner"}
    assert all(case.human_reviewed is True for case in cases)
    assert all(len(case.gold) == 3 for case in cases)
    for case in cases:
        for s in case.gold:
            assert case.text[s.start:s.end] == s.value
    assert prepare_e3c_clinical(source, output, verify_checkout=False) == manifest


def test_e3c_rejects_unpinned_source_by_default(tmp_path: Path):
    source = _e3c_fixture(tmp_path / "e3c")
    with pytest.raises(ValueError, match="Git checkout"):
        prepare_e3c_clinical(source, tmp_path / "out")


def test_e3c_uima_surrogate_offset_conversion_and_sofa_validation(tmp_path: Path):
    text = "🧬 diabete"
    assert _uima_to_python_offset(text, 2) == 1
    assert _uima_to_python_offset(text, 10) == len(text)
    with pytest.raises(ValueError, match="surrogate"):
        _uima_to_python_offset(text, 1)
    xml = tmp_path / "valid.xml"
    xml.write_text(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/XMI" '
        'xmlns:cas="http:///uima/cas.ecore" xmlns:custom="http:///webanno/custom.ecore">'
        '<cas:Sofa sofaString="🧬 diabete"/>'
        '<custom:CLINENTITY begin="3" end="10"/>'
        '</xmi:XMI>',
        encoding="utf-8",
    )
    assert e3c_clinical_entities(xml, text)[0]["value"] == "diabete"
    with pytest.raises(ValueError, match="Sofa"):
        e3c_clinical_entities(xml, "another sentence")
