from pathlib import Path

from redact_bench.documents import (
    add_e2e_fields,
    aggregate_e2e,
    aggregate_extraction,
    align_page_to_extraction,
    load_document_manifest,
)
from redact_bench.metrics import score_case
from redact_bench.models import Finding, InferenceResult


ROOT = Path(__file__).resolve().parents[1]


def test_document_manifest_loads_and_has_multiple_pages():
    documents = load_document_manifest(ROOT / "data/documents/manifest.jsonl")
    assert len(documents) == 5
    health = next(doc for doc in documents if doc.document_id == "doc-health-01")
    assert len(health.pages) == 2


def test_alignment_tracks_pii_lost_by_extraction():
    documents = load_document_manifest(ROOT / "data/documents/manifest.jsonl")
    page = documents[0].pages[0]
    extracted = "Scheda contatto cliente\nNome: Mario Rossi\nEmail rimossa dal parser"
    alignment = align_page_to_extraction(
        document_id="doc-general-01",
        profile="general",
        source_page=page,
        extracted_text=extracted,
    )
    assert alignment.source_gold_count == 5
    assert alignment.extraction_missed_count == 4
    assert len(alignment.case.gold) == 1


def test_e2e_recall_includes_extraction_misses():
    documents = load_document_manifest(ROOT / "data/documents/manifest.jsonl")
    page = documents[0].pages[0]
    extracted = "Scheda contatto cliente\nNome: Mario Rossi\nEmail rimossa dal parser"
    alignment = align_page_to_extraction(
        document_id="doc-general-01",
        profile="general",
        source_page=page,
        extracted_text=extracted,
    )
    gold = alignment.case.gold[0]
    result = InferenceResult(
        case_id=alignment.case.case_id,
        model="test-model",
        valid=True,
        latency_ms=10.0,
        findings=[
            Finding(
                pii_type=gold.pii_type,
                value=gold.value,
                start=gold.start,
                end=gold.end,
            )
        ],
        raw_content="{}",
    )
    score = score_case(alignment.case, result)
    row = add_e2e_fields(score, alignment, "doc-general-01")
    summary = aggregate_e2e([row])

    assert row["e2e_tp"] == 1
    assert row["e2e_fn"] == 4
    assert summary["e2e_pii_recall"] == 0.2
    assert summary["e2e_zero_leak_document_rate"] == 0.0


def test_extraction_aggregate_is_independent_from_model():
    rows = [
        {
            "source_gold_count": 5,
            "source_gold_chars": 50,
            "extraction_missed_count": 1,
            "extraction_missed_chars": 10,
            "extraction_text_similarity": 0.9,
            "page_missing": False,
        },
        {
            "source_gold_count": 3,
            "source_gold_chars": 30,
            "extraction_missed_count": 3,
            "extraction_missed_chars": 30,
            "extraction_text_similarity": 0.0,
            "page_missing": True,
        },
    ]
    summary = aggregate_extraction(rows)
    assert summary["extraction_entity_recall"] == 0.5
    assert summary["extraction_character_recall"] == 0.5
    assert summary["missing_pages"] == 1
