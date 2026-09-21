from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from redact_bench.models import Case, Span


STRUCTURE_MARKER_RE = re.compile(
    r"^\s*<!--\s*(page|sheet|slide|embedded-image)\s*:\s*(.*?)\s*-->\s*$"
)


def strip_structure_markers(text: str) -> str:
    """Build the exact model-input text used by the realistic dataset gold spans."""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not STRUCTURE_MARKER_RE.fullmatch(line.rstrip("\r\n"))
    )


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing dataset file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def validate_realistic_dataset(
    dataset_dir: str | Path,
    *,
    require_originals: bool = False,
) -> dict:
    root = Path(dataset_dir)
    manifest = _read_json(root / "manifest.json")
    documents = list(manifest.get("documents", []))
    if not documents:
        raise ValueError("Realistic dataset manifest contains no documents")

    canonical_dir = root / "canonical"
    annotations_dir = root / "annotations"
    originals_dir = root / "originals"

    total_spans = 0
    by_type: dict[str, int] = {}

    for document in documents:
        source_filename = str(document["source_filename"])
        canonical_filename = str(document["canonical_filename"])
        annotation_filename = str(
            document.get("annotation_filename") or f"{source_filename}.json"
        )

        canonical_path = canonical_dir / canonical_filename
        annotation_path = annotations_dir / annotation_filename

        try:
            canonical = canonical_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ValueError(f"Missing canonical Markdown: {canonical_path}") from exc

        annotation = _read_json(annotation_path)
        inference_text = strip_structure_markers(canonical)
        sha256 = hashlib.sha256(inference_text.encode("utf-8")).hexdigest()

        expected_chars = int(annotation["inference_text_chars"])
        expected_sha = str(annotation["inference_text_sha256"])
        if len(inference_text) != expected_chars:
            raise ValueError(
                f"{source_filename}: inference text length mismatch "
                f"({len(inference_text)} != {expected_chars})"
            )
        if sha256 != expected_sha:
            raise ValueError(
                f"{source_filename}: canonical/annotation SHA-256 mismatch "
                f"({sha256} != {expected_sha})"
            )

        manifest_sha = document.get("inference_text_sha256")
        if manifest_sha and str(manifest_sha) != expected_sha:
            raise ValueError(
                f"{source_filename}: manifest/annotation SHA-256 mismatch"
            )

        profile = str(annotation["profile"])
        manifest_profile = document.get("benchmark_profile")
        if manifest_profile and str(manifest_profile) != profile:
            raise ValueError(
                f"{source_filename}: manifest/annotation profile mismatch"
            )

        spans = list(annotation.get("spans", []))
        for index, span in enumerate(spans):
            start = int(span["start"])
            end = int(span["end"])
            value = str(span["value"])
            pii_type = str(span["pii_type"])
            if not 0 <= start < end <= len(inference_text):
                raise ValueError(
                    f"{source_filename}: invalid span bounds at index {index}: "
                    f"{start}:{end}"
                )
            if inference_text[start:end] != value:
                raise ValueError(
                    f"{source_filename}: span/value mismatch at index {index}: "
                    f"{inference_text[start:end]!r} != {value!r}"
                )
            total_spans += 1
            by_type[pii_type] = by_type.get(pii_type, 0) + 1

        manifest_span_count = document.get("annotation_span_count")
        if manifest_span_count is not None and int(manifest_span_count) != len(spans):
            raise ValueError(
                f"{source_filename}: manifest span count mismatch "
                f"({manifest_span_count} != {len(spans)})"
            )

        if require_originals and not (originals_dir / source_filename).exists():
            raise ValueError(
                f"Missing original source document: {originals_dir / source_filename}"
            )

    return {
        "dataset_id": manifest.get("dataset_id"),
        "documents": len(documents),
        "spans": total_spans,
        "by_type": dict(sorted(by_type.items())),
        "originals_required": require_originals,
    }


def load_realistic_dataset(dataset_dir: str | Path) -> list[Case]:
    root = Path(dataset_dir)
    validate_realistic_dataset(root)
    manifest = _read_json(root / "manifest.json")

    cases: list[Case] = []
    for document in manifest["documents"]:
        source_filename = str(document["source_filename"])
        canonical_filename = str(document["canonical_filename"])
        annotation_filename = str(
            document.get("annotation_filename") or f"{source_filename}.json"
        )
        canonical = (root / "canonical" / canonical_filename).read_text(encoding="utf-8")
        inference_text = strip_structure_markers(canonical)
        annotation = _read_json(root / "annotations" / annotation_filename)

        spans = tuple(
            Span(
                start=int(span["start"]),
                end=int(span["end"]),
                pii_type=str(span["pii_type"]),
                value=str(span["value"]),
            )
            for span in annotation.get("spans", [])
        )
        cases.append(
            Case(
                case_id=source_filename,
                profile=str(annotation["profile"]),
                text=inference_text,
                gold=spans,
                tags=(
                    "realistic-document",
                    str(document.get("source_mime_type", "unknown")),
                ),
            )
        )
    return cases
