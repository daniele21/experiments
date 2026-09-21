from __future__ import annotations

import textwrap
from pathlib import Path

from redact_bench.documents import DocumentCase


def generate_pdf_fixtures(documents: list[DocumentCase], output_dir: str | Path) -> list[Path]:
    """Generate deterministic synthetic PDFs from the committed canonical source text."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Document benchmark dependencies are missing. Run: uv sync --extra dev --extra documents"
        ) from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for document in documents:
        path = output / document.filename
        pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=0)
        width, height = A4

        for page in document.pages:
            text_obj = pdf.beginText()
            text_obj.setTextOrigin(54, height - 64)
            text_obj.setFont("Helvetica", 11)
            text_obj.setLeading(15)

            for logical_line in page.text.splitlines() or [""]:
                wrapped = textwrap.wrap(
                    logical_line,
                    width=92,
                    replace_whitespace=False,
                    drop_whitespace=False,
                ) or [""]
                for physical_line in wrapped:
                    text_obj.textLine(physical_line.rstrip())

            pdf.drawText(text_obj)
            pdf.showPage()

        pdf.save()
        written.append(path)

    return written
