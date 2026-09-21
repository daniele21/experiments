from __future__ import annotations

import json
import os
import platform
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from redact_bench.document_fixtures import generate_pdf_fixtures
from redact_bench.document_report import write_document_html
from redact_bench.docling_adapter import extract_pdf_pages
from redact_bench.documents import (
    PageAlignment,
    add_e2e_fields,
    aggregate_e2e,
    aggregate_extraction,
    align_page_to_extraction,
    load_document_manifest,
)
from redact_bench.metrics import aggregate, score_case
from redact_bench.models import InferenceResult
from redact_bench.provider import KorgisController, KorgisRedactProvider
from redact_bench.runner import (
    KORGIS_REPOSITORY,
    KORGIS_TESTED_REF,
    KORGIS_TESTED_SHA,
    REDACTGUARD_CONTRACT_SHA,
    REDACTGUARD_REPOSITORY,
    _git_sha,
)


def _missing_extraction_score(alignment: PageAlignment, model: str, reason: str) -> dict:
    return {
        "case_id": alignment.case.case_id,
        "profile": alignment.case.profile,
        "model": model,
        "valid": False,
        "latency_ms": 0.0,
        "gold_count": len(alignment.case.gold),
        "predicted_count": 0,
        "tp": 0,
        "exact_tp": 0,
        "overlap_tp": 0,
        "fp": 0,
        "fn": len(alignment.case.gold),
        "zero_leak": False,
        "leaked_chars": sum(span.end - span.start for span in alignment.case.gold),
        "gold_chars": sum(span.end - span.start for span in alignment.case.gold),
        "overredacted_chars": 0,
        "non_pii_chars": max(
            1,
            len(alignment.case.text)
            - sum(span.end - span.start for span in alignment.case.gold),
        ),
        "input_tokens": None,
        "output_tokens": None,
        "error": reason,
    }


def run_document_compare(
    *,
    models: list[str],
    manifest_path: str,
    profiles_path: str,
    fixtures_dir: str,
    results_dir: str,
    generate_fixtures: bool = True,
    warmups: int = 1,
) -> Path:
    documents = load_document_manifest(manifest_path)
    fixture_root = Path(fixtures_dir)
    if generate_fixtures:
        generate_pdf_fixtures(documents, fixture_root)

    missing_files = [
        str(fixture_root / doc.filename)
        for doc in documents
        if not (fixture_root / doc.filename).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            "Missing document fixtures: "
            + ", ".join(missing_files)
            + ". Run the fixture generator or provide the PDFs."
        )

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-documents-"
        + uuid.uuid4().hex[:8]
    )
    output = Path(results_dir) / run_id
    output.mkdir(parents=True, exist_ok=True)

    alignment_records: list[tuple[str, int, bool, PageAlignment]] = []
    extraction_rows: list[dict] = []
    extracted_evidence: dict[str, dict] = {}
    extra_pages = 0

    for document in documents:
        pdf_path = fixture_root / document.filename
        extracted_pages = extract_pdf_pages(pdf_path)
        by_page = {page.page_number: page for page in extracted_pages}
        extra_pages += max(0, len(extracted_pages) - len(document.pages))
        extracted_evidence[document.document_id] = {
            "filename": document.filename,
            "source_page_count": len(document.pages),
            "extracted_page_count": len(extracted_pages),
            "pages": [asdict(page) for page in extracted_pages],
        }

        for source_page in document.pages:
            extracted = by_page.get(source_page.page_number)
            page_missing = extracted is None
            extracted_text = "" if extracted is None else extracted.text
            alignment = align_page_to_extraction(
                document_id=document.document_id,
                profile=document.profile,
                source_page=source_page,
                extracted_text=extracted_text,
            )
            alignment_records.append(
                (document.document_id, source_page.page_number, page_missing, alignment)
            )
            extraction_rows.append(
                {
                    "document_id": document.document_id,
                    "page_number": source_page.page_number,
                    "page_missing": page_missing,
                    "source_gold_count": alignment.source_gold_count,
                    "source_gold_chars": alignment.source_gold_chars,
                    "extraction_missed_count": alignment.extraction_missed_count,
                    "extraction_missed_chars": alignment.extraction_missed_chars,
                    "extraction_text_similarity": alignment.extraction_text_similarity,
                }
            )

    extraction_summary = aggregate_extraction(extraction_rows)
    extraction_summary["extra_pages"] = extra_pages
    (output / "extraction.json").write_text(
        json.dumps(
            {
                "summary": extraction_summary,
                "rows": extraction_rows,
                "documents": extracted_evidence,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    controller = KorgisController()
    controller.health()
    model_summaries: dict[str, dict] = {}
    identities: dict[str, dict | None] = {}
    all_rows: list[dict] = []

    runnable_alignments = [
        alignment
        for _, _, page_missing, alignment in alignment_records
        if not page_missing and alignment.case.text.strip()
    ]

    for model in models:
        controller.activate(model)
        identities[model] = controller.model_identity(model)
        provider = KorgisRedactProvider(model, profiles_path)

        for alignment in runnable_alignments[: min(warmups, len(runnable_alignments))]:
            provider.evaluate(alignment.case)

        model_quality_rows: list[dict] = []
        model_e2e_rows: list[dict] = []
        raw_path = output / f"{model.replace('/', '_')}.jsonl"

        with raw_path.open("w", encoding="utf-8") as raw_file:
            for document_id, page_number, page_missing, alignment in alignment_records:
                extraction_unusable = page_missing or not alignment.case.text.strip()
                if extraction_unusable:
                    score = _missing_extraction_score(
                        alignment,
                        model,
                        "extraction_missing_page" if page_missing else "extraction_empty_page",
                    )
                    result_dict = {
                        "case_id": alignment.case.case_id,
                        "model": model,
                        "valid": False,
                        "latency_ms": 0.0,
                        "findings": [],
                        "raw_content": "",
                        "error": score["error"],
                    }
                else:
                    result: InferenceResult = provider.evaluate(alignment.case)
                    score = score_case(alignment.case, result)
                    model_quality_rows.append(score)
                    result_dict = result.to_dict()

                e2e_row = add_e2e_fields(score, alignment, document_id)
                e2e_row["page_number"] = page_number
                e2e_row["page_missing"] = page_missing
                model_e2e_rows.append(e2e_row)
                all_rows.append(e2e_row)

                raw_file.write(
                    json.dumps(
                        {
                            "document_id": document_id,
                            "page_number": page_number,
                            "source_gold_count": alignment.source_gold_count,
                            "mapped_gold": [asdict(span) for span in alignment.case.gold],
                            "extraction_missed_count": alignment.extraction_missed_count,
                            "extraction_text_similarity": alignment.extraction_text_similarity,
                            "result": result_dict,
                            "score": e2e_row,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        model_summaries[model] = {
            "model_on_extracted_text": aggregate(model_quality_rows),
            "end_to_end": aggregate_e2e(model_e2e_rows),
        }

    manifest = {
        "run_id": run_id,
        "kind": "document-end-to-end",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_commit": _git_sha(),
        "document_manifest": str(Path(manifest_path)),
        "fixtures_dir": str(fixture_root),
        "documents": [doc.document_id for doc in documents],
        "models": models,
        "warmups_per_model": warmups,
        "extraction": {
            "engine": "docling",
            "contract": "mirrors RedactGuard anonimizer/services/pdf_converter.py",
            "summary": extraction_summary,
        },
        "korgis": {
            "repository": KORGIS_REPOSITORY,
            "tested_ref": KORGIS_TESTED_REF,
            "tested_sha": KORGIS_TESTED_SHA,
            "base_url": os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1"),
            "runtime_identity": identities,
        },
        "redactguard_contract": {
            "repository": REDACTGUARD_REPOSITORY,
            "source_sha": REDACTGUARD_CONTRACT_SHA,
            "scope": "Docling page extraction + prompt taxonomy + deterministic post-processing",
        },
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }

    (output / "metrics.json").write_text(
        json.dumps(
            {"extraction": extraction_summary, "models": model_summaries},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output / "rows.json").write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_document_html(output / "report.html", extraction_summary, model_summaries, manifest)
    return output
