from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from redact_bench.models import Case, Span


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    gold: tuple[Span, ...]


@dataclass(frozen=True)
class DocumentCase:
    document_id: str
    filename: str
    profile: str
    pages: tuple[DocumentPage, ...]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class PageAlignment:
    case: Case
    source_gold_count: int
    source_gold_chars: int
    extraction_missed_count: int
    extraction_missed_chars: int
    extraction_text_similarity: float


def _resolve_entities(text: str, entities: list[dict]) -> tuple[Span, ...]:
    spans: list[Span] = []
    for entity in entities:
        value = str(entity["value"])
        pii_type = str(entity["pii_type"])
        start = 0
        found = 0
        while True:
            idx = text.find(value, start)
            if idx < 0:
                break
            spans.append(Span(idx, idx + len(value), pii_type, value))
            found += 1
            if not entity.get("all_occurrences", False):
                break
            start = idx + len(value)
        if found == 0:
            raise ValueError(f"Gold entity {value!r} not present in document source text")
    unique = {(s.start, s.end, s.pii_type): s for s in spans}
    return tuple(sorted(unique.values(), key=lambda s: (s.start, s.end, s.pii_type)))


def load_document_manifest(path: str | Path) -> list[DocumentCase]:
    documents: list[DocumentCase] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            pages: list[DocumentPage] = []
            for raw_page in row.get("pages", []):
                text = str(raw_page["text"])
                pages.append(
                    DocumentPage(
                        page_number=int(raw_page["page_number"]),
                        text=text,
                        gold=_resolve_entities(text, list(raw_page.get("entities", []))),
                    )
                )
            if not pages:
                raise ValueError(f"Document at line {line_number} has no pages")
            documents.append(
                DocumentCase(
                    document_id=str(row["id"]),
                    filename=str(row["filename"]),
                    profile=str(row["profile"]),
                    pages=tuple(sorted(pages, key=lambda p: p.page_number)),
                    tags=tuple(str(x) for x in row.get("tags", [])),
                )
            )

    ids = [doc.document_id for doc in documents]
    filenames = [doc.filename for doc in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Document manifest contains duplicate ids")
    if len(filenames) != len(set(filenames)):
        raise ValueError("Document manifest contains duplicate filenames")
    return documents


def _normalized_pattern(value: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in value.split() if part]
    if not parts:
        return re.compile(r"(?!x)x")
    return re.compile(r"\s+".join(parts))


def _normalize_for_similarity(text: str) -> str:
    return " ".join(text.split())


def align_page_to_extraction(
    *,
    document_id: str,
    profile: str,
    source_page: DocumentPage,
    extracted_text: str,
) -> PageAlignment:
    grouped_occurrence: dict[tuple[str, str], int] = {}
    mapped: list[Span] = []
    missed_count = 0
    missed_chars = 0

    for source_span in source_page.gold:
        key = (source_span.pii_type, source_span.value)
        occurrence = grouped_occurrence.get(key, 0)
        grouped_occurrence[key] = occurrence + 1

        matches = list(_normalized_pattern(source_span.value).finditer(extracted_text))
        if occurrence >= len(matches):
            missed_count += 1
            missed_chars += source_span.end - source_span.start
            continue

        match = matches[occurrence]
        mapped.append(
            Span(
                start=match.start(),
                end=match.end(),
                pii_type=source_span.pii_type,
                value=extracted_text[match.start() : match.end()],
            )
        )

    source_norm = _normalize_for_similarity(source_page.text)
    extracted_norm = _normalize_for_similarity(extracted_text)
    similarity = SequenceMatcher(None, source_norm, extracted_norm).ratio()

    return PageAlignment(
        case=Case(
            case_id=f"{document_id}:p{source_page.page_number}",
            profile=profile,
            text=extracted_text,
            gold=tuple(mapped),
            tags=("document-e2e",),
        ),
        source_gold_count=len(source_page.gold),
        source_gold_chars=sum(span.end - span.start for span in source_page.gold),
        extraction_missed_count=missed_count,
        extraction_missed_chars=missed_chars,
        extraction_text_similarity=similarity,
    )


def aggregate_extraction(rows: list[dict]) -> dict:
    source_gold = sum(row["source_gold_count"] for row in rows)
    missed = sum(row["extraction_missed_count"] for row in rows)
    source_chars = sum(row["source_gold_chars"] for row in rows)
    missed_chars = sum(row["extraction_missed_chars"] for row in rows)
    similarities = [row["extraction_text_similarity"] for row in rows]
    missing_pages = sum(bool(row["page_missing"]) for row in rows)

    return {
        "pages": len(rows),
        "missing_pages": missing_pages,
        "source_gold_count": source_gold,
        "extracted_gold_count": source_gold - missed,
        "extraction_entity_recall": (source_gold - missed) / source_gold if source_gold else 1.0,
        "extraction_character_recall": (
            (source_chars - missed_chars) / source_chars if source_chars else 1.0
        ),
        "mean_text_similarity": sum(similarities) / len(similarities) if similarities else 0.0,
    }


def add_e2e_fields(score: dict, alignment: PageAlignment, document_id: str) -> dict:
    row = dict(score)
    source_gold_count = alignment.source_gold_count
    extraction_missed = alignment.extraction_missed_count

    row.update(
        {
            "document_id": document_id,
            "source_gold_count": source_gold_count,
            "source_gold_chars": alignment.source_gold_chars,
            "extraction_missed_count": extraction_missed,
            "extraction_missed_chars": alignment.extraction_missed_chars,
            "extraction_text_similarity": alignment.extraction_text_similarity,
            "e2e_tp": score["tp"],
            "e2e_fn": score["fn"] + extraction_missed,
            "e2e_leaked_chars": score["leaked_chars"] + alignment.extraction_missed_chars,
            "e2e_gold_chars": score["gold_chars"] + alignment.extraction_missed_chars,
            "e2e_zero_leak": bool(
                score["zero_leak"] and extraction_missed == 0
            ),
        }
    )
    return row


def aggregate_e2e(rows: list[dict]) -> dict:
    if not rows:
        return {
            "pages": 0,
            "documents": 0,
            "e2e_pii_recall": 0.0,
            "e2e_leakage_rate": 0.0,
            "e2e_zero_leak_document_rate": 0.0,
        }

    tp = sum(row["e2e_tp"] for row in rows)
    fn = sum(row["e2e_fn"] for row in rows)
    leaked_chars = sum(row["e2e_leaked_chars"] for row in rows)
    gold_chars = sum(row["e2e_gold_chars"] for row in rows)

    per_document: dict[str, bool] = {}
    for row in rows:
        per_document[row["document_id"]] = per_document.get(row["document_id"], True) and bool(
            row["e2e_zero_leak"]
        )

    return {
        "pages": len(rows),
        "documents": len(per_document),
        "e2e_pii_recall": tp / (tp + fn) if tp + fn else 1.0,
        "e2e_leakage_rate": leaked_chars / gold_chars if gold_chars else 0.0,
        "e2e_zero_leak_document_rate": (
            sum(per_document.values()) / len(per_document) if per_document else 0.0
        ),
    }
