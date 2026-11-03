"""Public, independently annotated clinical NER benchmark adapters.

No synthetic clinical labels are generated. This is *not* PII anonymization gold.
SPACCC joins published test annotations to independently published full texts;
E3C uses the official Italian Layer-1 test partition and UIMA XML labels.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import xml.etree.ElementTree as ET

from redact_bench.e3c import SOURCE_SHA as E3C_SOURCE_SHA, _rows as e3c_rows

SPACCC_LABELS = {
    "DISEASE": "clinical_disease",
    "SYMPTOM": "clinical_symptom",
    "PROCEDURE": "clinical_procedure",
    "CHEMICAL": "clinical_chemical",
    "PROTEIN": "clinical_protein",
}
E3C_LABELS = {
    "CLINENTITY": "e3c_clinical_entity",
    "BODYPART": "e3c_body_part",
    "RML": "e3c_measurement",
    "ACTOR": "e3c_actor",
}
SEED = 20261103


def _hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def _read_records(path: Path) -> list[dict]:
    """Support Parquet for actual public data, JSONL only for offline fixtures."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing source: {path}")
    if path.suffix == ".jsonl":
        result = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
                  if x.strip()]
    elif path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet requires pyarrow; use uv run --with pyarrow") from exc
        result = pq.read_table(path).to_pylist()
    else:
        raise ValueError("Expected .parquet source or .jsonl fixture")
    if not result or not all(isinstance(row, dict) for row in result):
        raise ValueError("Source has no usable records")
    return result


def _write(output: Path, cases: list[dict], manifest: dict) -> dict:
    if not cases:
        raise ValueError("No benchmark cases")
    # Dataset identity changes with each source/selection; old and new
    # benchmarks may never be silently mixed in the model x dataset UI.
    canonical = [
        (r["id"], _hash(r["text"].encode("utf-8")), r["entities"]) for r in cases
    ]
    fingerprint = _hash(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode())
    version = str(manifest["gold_version_prefix"]) + "-" + fingerprint[:12]
    for r in cases:
        r["gold_version"] = version
    output.mkdir(parents=True, exist_ok=True)
    target = output / "cases.jsonl"
    with target.open("w", encoding="utf-8") as file:
        for r in cases:
            file.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        **manifest, "gold_version": version, "selection_sha256": fingerprint,
        "cases": len(cases), "gold_spans": sum(len(r["entities"]) for r in cases),
        "by_label": dict(sorted(Counter(
            e["pii_type"] for r in cases for e in r["entities"]
        ).items())),
        "note": "Clinical entities are not automatically PII; score NER only.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _stem(name: str) -> str:
    # Annotation filename: S0004-...-1
    # Documents filename: es-S0004-...-1.txt
    return Path(name).name.removeprefix("es-").removesuffix(".txt")


def prepare_spaccc(
    annotations_file: Path, documents_file: Path, output_dir: Path, *,
    limit: int = 200,
) -> dict:
    """Join HF *test* entity mentions to full docs; verify every exact gold offset.

    Never read annotation train data. Documents repo has only a train-named
    source split, which contains all original documents and is NOT NER training.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    if not annotations_file.name.startswith("test-"):
        raise ValueError("SPACCC labels must come from the official test-* split")
    annotations = _read_records(annotations_file)
    documents = _read_records(documents_file)
    doc_index: dict[str, str] = {}
    for row in documents:
        if not isinstance(row.get("document"), str) or not row["document"]:
            raise ValueError("SPACCC document row missing text")
        key = _stem(str(row["filename"]))
        if key in doc_index:
            raise ValueError(f"Duplicate SPACCC original document: {key}")
        doc_index[key] = row["document"]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in annotations:
        key = _stem(str(row["filename"]))
        grouped[key].append(row)
    if len(grouped) < limit:
        raise ValueError(f"Only {len(grouped)} test documents; requested {limit}")

    cases, rejected = [], []
    for key, rows in sorted(grouped.items()):
        if key not in doc_index:
            rejected.append({"document": key, "reason": "original_document_missing"})
            continue
        original = doc_index[key]
        entities = []
        try:
            for row in rows:
                label = str(row["label"])
                if label not in SPACCC_LABELS:
                    raise ValueError(f"Unknown clinical label {label}")
                start, end = row["start_span"], row["end_span"]
                value = row["text"]
                if type(start) is not int or type(end) is not int or not isinstance(value, str):
                    raise ValueError("Invalid gold span shape")
                if not 0 <= start < end <= len(original) or original[start:end] != value:
                    raise ValueError(f"Offset mismatch for {label} [{start}:{end}]")
                entities.append({
                    "start": start, "end": end, "value": value,
                    "pii_type": SPACCC_LABELS[label], "pii_subtype": label,
                })
            # Keep distinct labels for identical spans and retain nested/cross-
            # class annotations, as present in upstream source. Only drop exact
            # duplicate records from the merged tables.
            unique = {(e["start"], e["end"], e["pii_type"]): e for e in entities}
            ordered = sorted(unique.values(), key=lambda e: (
                e["start"], e["end"], e["pii_type"],
            ))
            if not ordered:
                raise ValueError("No clinical labels")
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"document": key, "reason": str(exc)})
            continue
        cases.append({
            "id": "spaccc-test-" + key, "profile": "spaccc_clinical_ner",
            "text": original, "entities": ordered, "gold_scope": "complete",
            "tags": ["clinical_ner", "spaccc", "es", "original", "not_pii"],
            "content_family_id": key, "variant_id": "gold-test",
            "human_reviewed": None,
        })

    if len(cases) < limit:
        raise ValueError(
            f"Only {len(cases)} exact-aligned test documents of {len(grouped)}; "
            f"need {limit}. Rejected: {rejected[:5]}"
        )
    rng = random.Random(SEED)
    rng.shuffle(cases)
    selected = sorted(cases[:limit], key=lambda r: r["id"])
    return _write(output_dir, selected, {
        "dataset": "SPACCC-Spanish-NER",
        "task": "clinical_ner_not_patient_privacy",
        "language": "es", "split": "test_annotations_only",
        "gold_version_prefix": "spaccc_es_clinical_gold_v1",
        "annotation_source": "IEETA/SPACCC-Spanish-NER",
        "document_source": "IEETA/SPACCC-documents",
        "annotation_source_sha256": _hash(annotations_file.read_bytes()),
        "document_source_sha256": _hash(documents_file.read_bytes()),
        "license": "CC BY 4.0", "sampling_seed": SEED,
        "test_documents_total": len(grouped),
        "eligible_documents": len(cases),
        "excluded_documents": rejected,
        "labels": list(SPACCC_LABELS),
        "overlapping_spans_per_document_allowed": True,
        "clinical_label_taxonomy": "disease,symptom,procedure,chemical,protein",
        "important": "CHEMICAL is not interchangeable with prescribed medication.",
    })


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _uima_to_python_offset(text: str, offset: int) -> int:
    """UIMA XMI offsets use Java UTF-16 units; Python strings use codepoints."""
    if offset < 0:
        raise ValueError("Negative UIMA offset")
    units = 0
    for index, ch in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > offset:
            raise ValueError("UIMA offset splits a surrogate pair")
    if units == offset:
        return len(text)
    raise ValueError("UIMA offset exceeds the sofa length")


def e3c_clinical_entities(xml_path: Path, text: str) -> list[dict]:
    """Only independently annotated E3C entity layers, not temporal EVENT verbs."""
    root = ET.parse(xml_path).getroot()
    sofa = [e for e in root.iter() if _local(e.tag) == "Sofa"]
    if len(sofa) != 1 or sofa[0].attrib.get("sofaString", "").rstrip("\r\n") != text:
        raise ValueError("E3C UIMA Sofa does not match canonical source text")
    spans = []
    for el in root:
        label = _local(el.tag)
        if label not in E3C_LABELS:
            continue
        begin, end = _uima_to_python_offset(text, int(el.attrib["begin"])), (
            _uima_to_python_offset(text, int(el.attrib["end"]))
        )
        if not 0 <= begin < end <= len(text):
            raise ValueError("Invalid E3C entity span")
        spans.append({
            "start": begin, "end": end, "value": text[begin:end],
            "pii_type": E3C_LABELS[label], "pii_subtype": label,
        })
    result = {
        (r["start"], r["end"], r["pii_type"]): r for r in spans
    }
    return sorted(result.values(), key=lambda e: (
        e["start"], e["end"], e["pii_type"],
    ))


def prepare_e3c_clinical(source_dir: Path, output_dir: Path) -> dict:
    """Use E3C test split already verified by the E3C importer, no injections."""
    # e3c_rows verifies all 86 Italian narratives, their paired XML files,
    # the official 36/50 split, and returns originals without synthetic PII.
    original, _, _ = e3c_rows(source_dir)
    cases = []
    for row in original:
        entities = e3c_clinical_entities(
            source_dir / "data_annotation/Italian/layer1" / (row["source_id"] + ".xml"),
            row["text"],
        )
        cases.append({
            "id": "e3c-clinical-" + row["source_id"],
            "profile": "e3c_clinical_ner",
            "text": row["text"], "entities": entities,
            "gold_scope": "complete",
            "tags": ["e3c", "clinical_ner", "it", "gold_test", "not_pii"],
            "content_family_id": row["content_family_id"],
            "variant_id": "clinical-gold", "human_reviewed": True,
        })
    if len(cases) != 50:
        raise ValueError("Expected exactly 50 E3C Italian Layer-1 test documents")
    if not any(case["entities"] for case in cases):
        raise ValueError("E3C original XML has no clinical gold")
    return _write(output_dir, cases, {
        "dataset": "E3C Italian clinical gold",
        "task": "clinical_ner_not_patient_privacy",
        "language": "it", "split": "official_layer1_test",
        "source": "hltfbk/E3C-Corpus", "source_sha": E3C_SOURCE_SHA,
        "source_license": "CC BY-NC", "license": "CC BY-NC",
        "gold_version_prefix": "e3c_it_clinical_gold_v1",
        "labels": list(E3C_LABELS),
        "important": "CLINENTITY covers UMLS clinical disorders; ACTOR is a reference to a human/animal, not a person's identity. EVENT is intentionally excluded.",
    })
