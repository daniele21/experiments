import hashlib
import json
from pathlib import Path

import pytest

from redact_bench.realistic_dataset import (
    load_realistic_dataset,
    strip_structure_markers,
    validate_realistic_dataset,
)


def _write_fixture(root: Path) -> Path:
    canonical_dir = root / "canonical"
    annotations_dir = root / "annotations"
    canonical_dir.mkdir(parents=True)
    annotations_dir.mkdir(parents=True)

    canonical = "<!-- page: 1 -->\n\nMario Rossi | mario@example.com\n"
    inference = strip_structure_markers(canonical)
    assert inference == "\nMario Rossi | mario@example.com\n"

    spans = [
        {
            "start": inference.index("Mario Rossi"),
            "end": inference.index("Mario Rossi") + len("Mario Rossi"),
            "pii_type": "private_person",
            "value": "Mario Rossi",
        },
        {
            "start": inference.index("mario@example.com"),
            "end": inference.index("mario@example.com") + len("mario@example.com"),
            "pii_type": "private_email",
            "value": "mario@example.com",
        },
    ]
    sha = hashlib.sha256(inference.encode("utf-8")).hexdigest()

    (canonical_dir / "sample.pdf.md").write_text(canonical, encoding="utf-8")
    (annotations_dir / "sample.pdf.json").write_text(
        json.dumps(
            {
                "schema_version": "redactguard-gold-v1",
                "canonical_filename": "sample.pdf.md",
                "profile": "legal",
                "inference_text_chars": len(inference),
                "inference_text_sha256": sha,
                "spans": spans,
            }
        ),
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "test-realistic",
                "documents": [
                    {
                        "source_filename": "sample.pdf",
                        "source_mime_type": "application/pdf",
                        "canonical_filename": "sample.pdf.md",
                        "annotation_filename": "sample.pdf.json",
                        "benchmark_profile": "legal",
                        "annotation_span_count": 2,
                        "inference_text_sha256": sha,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_validate_and_load_realistic_dataset(tmp_path):
    root = _write_fixture(tmp_path)
    summary = validate_realistic_dataset(root)
    assert summary["documents"] == 1
    assert summary["spans"] == 2

    cases = load_realistic_dataset(root)
    assert len(cases) == 1
    assert cases[0].case_id == "sample.pdf"
    assert cases[0].profile == "legal"
    assert len(cases[0].gold) == 2
    assert "<!-- page:" not in cases[0].text


def test_require_originals(tmp_path):
    root = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="Missing original"):
        validate_realistic_dataset(root, require_originals=True)

    originals = root / "originals"
    originals.mkdir()
    (originals / "sample.pdf").write_bytes(b"%PDF-test")
    validate_realistic_dataset(root, require_originals=True)


def test_validation_fails_when_canonical_drifts(tmp_path):
    root = _write_fixture(tmp_path)
    path = root / "canonical" / "sample.pdf.md"
    path.write_text(path.read_text(encoding="utf-8") + "drift", encoding="utf-8")

    with pytest.raises(ValueError, match="mismatch"):
        validate_realistic_dataset(root)
