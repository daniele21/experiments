from __future__ import annotations

import os
from pathlib import Path

from redact_bench.documents import ExtractedPage


def build_docling_converter():
    """Mirror the active RedactGuard Docling converter contract."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError(
            "Document benchmark dependencies are missing. Run: uv sync --extra dev --extra documents"
        ) from exc

    artifacts_path = os.getenv("DOCLING_ARTIFACTS_PATH")
    if artifacts_path:
        return DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            artifacts_path=artifacts_path,
        )
    return DocumentConverter(allowed_formats=[InputFormat.PDF])


def extract_pdf_pages(path: str | Path) -> list[ExtractedPage]:
    converter = build_docling_converter()
    result = converter.convert(Path(path))
    doc = result.document
    page_count = getattr(result.input, "page_count", 0) or len(
        getattr(result, "pages", []) or []
    )

    if page_count <= 0:
        return [ExtractedPage(page_number=1, text=doc.export_to_markdown().strip())]

    return [
        ExtractedPage(
            page_number=page_number,
            text=doc.export_to_markdown(page_no=page_number).strip(),
        )
        for page_number in range(1, page_count + 1)
    ]
