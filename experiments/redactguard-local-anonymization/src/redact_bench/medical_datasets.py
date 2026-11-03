"""Opt-in gold adapters for three different medical benchmark tasks.

All source content remains in the ignored local cache. Never combine their
scores: ASQ/MEDDOCAN measure PHI; PharmaER measures clinical term extraction.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
from urllib.request import urlopen

ASQ_REVISION = "fdb371ce7e3908a945d82f20411546b9876f862e"
ASQ_URL = (
    "https://raw.githubusercontent.com/JamesWeatherhead/asq-phi/"
    + ASQ_REVISION + "/data/synthetic_clinical_queries.txt"
)
ASQ_TYPES = frozenset({
    "NAME", "GEOGRAPHIC_LOCATION", "DATE", "MEDICAL_RECORD_NUMBER",
    "HEALTH_PLAN_BENEFICIARY_NUMBER", "PHONE_NUMBER", "SOCIAL_SECURITY_NUMBER",
    "EMAIL_ADDRESS", "UNIQUE_IDENTIFIER", "ACCOUNT_NUMBER", "FAX_NUMBER",
    "CERTIFICATE_LICENSE_NUMBER", "IP_ADDRESS",
})
CLINICAL_TYPES = frozenset({"DRUG", "DISEASE", "SYMPTOM", "ANATOMICAL_PART"})
MEDDOCAN_MAP = {
    "NOMBRE_SUJETO_ASISTENCIA": "med_name",
    "NOMBRE_PERSONAL_SANITARIO": "med_name",
    "FECHAS": "med_date",
    "EDAD_SUJETO_ASISTENCIA": "med_age",
    "CALLE": "med_location",
    "HOSPITAL": "med_location",
    "INSTITUCION": "med_location",
    "CENTRO_SALUD": "med_location",
    "TERRITORIO": "med_location",
    "PAIS": "med_location",
    "NUMERO_TELEFONO": "med_contact",
    "NUMERO_FAX": "med_contact",
    "CORREO": "med_contact",
    "CORREO_ELECTRONICO": "med_contact",
    "URL_WEB": "med_contact",
    "DIREC_PROT_INTERNET": "med_contact",
    "PROFESION": "med_profession",
    "SEXO_SUJETO_ASISTENCIA": "med_other",
    "FAMILIARES_SUJETO_ASISTENCIA": "med_other",
    "OTROS_SUJETO_ASISTENCIA": "med_other",
    "ID_SUJETO_ASISTENCIA": "med_id",
    "ID_CONTACTO_ASISTENCIAL": "med_id",
    "ID_ASEGURAMIENTO": "med_id",
    "NUMERO_BENEF_PLAN_SALUD": "med_id",
    "ID_TITULACION_PERSONAL_SANITARIO": "med_id",
    "ID_EMPLEO_PERSONAL_SANITARIO": "med_id",
    "OTRO_NUMERO_IDENTIF": "med_id",
    "NUMERO_IDENTIF": "med_id",
    "IDENTIF_VEHICULOS_NRSERIE_PLACAS": "med_id",
    "IDENTIF_DISPOSITIVOS_NRSERIE": "med_id",
    "IDENTIF_BIOMETRICOS": "med_id",
}


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _write(output: Path, rows: list[dict], manifest: dict) -> dict:
    if not rows:
        raise ValueError("No valid benchmark cases; refusing to create an empty dataset")
    # Dataset identity includes selected case IDs, content AND gold annotations.
    # A 10-case smoke run must never merge with a 120-case quality benchmark.
    selection = json.dumps(
        [(row["id"], _digest(row["text"].encode("utf-8")), row["entities"]) for row in rows],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    selection_sha = _digest(selection)
    for row in rows:
        row["gold_version"] += "-" + selection_sha[:12]
    manifest = {**manifest, "selection_sha256": selection_sha}
    output.mkdir(parents=True, exist_ok=True)
    dest = output / "cases.jsonl"
    with dest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {**manifest, "cases": len(rows), "gold_count": sum(len(r["entities"]) for r in rows)}
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def fetch_asq(destination: Path) -> Path:
    """Download a pinned public MIT-licensed source; no model inference."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(ASQ_URL, timeout=45) as response:
        blob = response.read(5_000_001)
    if len(blob) > 5_000_000 or not blob.startswith(b"===QUERY==="):
        raise ValueError("Invalid ASQ-PHI source payload")
    destination.write_bytes(blob)
    return destination


def _asq_blocks(content: str) -> list[tuple[str, list[dict]]]:
    if not content.startswith("===QUERY==="):
        raise ValueError("Invalid ASQ source: missing initial query delimiter")
    rows = []
    for block in content.split("===QUERY===")[1:]:
        if block.count("===PHI_TAGS===") != 1:
            raise ValueError("Invalid ASQ record structure")
        raw_query, raw_tags = block.split("===PHI_TAGS===")
        query = raw_query.strip()
        if not query:
            raise ValueError("Empty query in ASQ source")
        tags = []
        for line in raw_tags.splitlines():
            line = line.strip()
            if not line:
                continue
            tag = json.loads(line)
            if not isinstance(tag, dict) or set(tag) != {"identifier_type", "value"}:
                raise ValueError("Invalid ASQ tag schema")
            if tag["identifier_type"] not in ASQ_TYPES or not isinstance(tag["value"], str):
                raise ValueError("Unknown ASQ label or value")
            tags.append(tag)
        rows.append((query, tags))
    return rows


def _asq_entities(query: str, tags: list[dict]) -> list[dict]:
    """Fail closed on ambiguous repeated strings: source supplies values, not offsets."""
    values = Counter(t["value"] for t in tags)
    result = []
    for value, repetitions in values.items():
        if not value:
            raise ValueError("Empty ASQ tag")
        matches = [m.start() for m in re.finditer(re.escape(value), query)]
        if len(matches) != repetitions:
            raise ValueError("ASQ value does not have unique/complete offset alignment")
        corresponding = [t for t in tags if t["value"] == value]
        if len({t["identifier_type"] for t in corresponding}) != 1:
            raise ValueError("ASQ repeated value has ambiguous tag types")
        for start in matches:
            result.append({
                "start": start, "end": start + len(value),
                "value": value, "pii_type": corresponding[0]["identifier_type"].lower(),
                "pii_subtype": corresponding[0]["identifier_type"],
            })
    ordered = sorted(result, key=lambda e: (e["start"], e["end"]))
    if any(a["end"] > b["start"] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping ASQ gold spans")
    return ordered


def prepare_asq(source: Path, output: Path, *, positives: int = 96,
                negatives: int = 24, strict_size: bool = True) -> dict:
    if positives < 0 or negatives < 0 or positives + negatives == 0:
        raise ValueError("Select at least one case and nonnegative quotas")
    blob = source.read_bytes()
    parsed = _asq_blocks(blob.decode("utf-8-sig"))
    if strict_size and (len(parsed) != 1051 or sum(bool(t) for _, t in parsed) != 832):
        raise ValueError("Pinned ASQ source does not match published corpus counts")
    valid = {True: [], False: []}
    excluded = []
    for index, (query, tags) in enumerate(parsed, 1):
        try:
            entities = _asq_entities(query, tags)
        except ValueError as exc:
            excluded.append({"index": index, "reason": str(exc)})
            continue
        row = {
            "id": f"asq-{index:04d}", "profile": "asq_phi",
            "text": query, "entities": entities, "gold_scope": "complete",
            "gold_version": "asq_phi_hipaa_13_v1",
            "tags": ["medical", "asq_phi", "en", "positive" if tags else "hard_negative"],
            "human_reviewed": False,
        }
        valid[bool(tags)].append(row)
    rng = random.Random(20261103)
    for collection in valid.values():
        rng.shuffle(collection)
    if len(valid[True]) < positives or len(valid[False]) < negatives:
        raise ValueError("Insufficient unambiguous ASQ records for requested quotas")
    selected = sorted(valid[True][:positives] + valid[False][:negatives], key=lambda r: r["id"])
    return _write(output, selected, {
        "dataset": "ASQ-PHI", "task": "phi_deidentification",
        "label_space": "original_13_HIPAA_types_no_mapping",
        "source": ASQ_URL, "source_sha256": _digest(blob),
        "license": "MIT", "source_records": len(parsed),
        "available_positives": len(valid[True]), "available_negatives": len(valid[False]),
        "excluded_ambiguous_records": excluded,
        "selected_positives": positives, "selected_negatives": negatives,
        "sampling_seed": 20261103, "not_comparable_to": ["pharmaer_clinical_ner", "e3c_injected"],
    })


def _meddocan_entities(text: str, ann: str) -> list[dict]:
    gold = []
    for line in ann.splitlines():
        if not line.startswith("T"):
            continue  # relations, attributes and notes are not PHI mentions
        columns = line.split("\t")
        if len(columns) != 3:
            raise ValueError("Invalid BRAT entity line")
        metadata = columns[1].split()
        if len(metadata) != 3:  # discontinuous BRAT spans need explicit handling
            raise ValueError("Unsupported discontinuous BRAT entity")
        kind, start, end = metadata
        if kind not in MEDDOCAN_MAP:
            raise ValueError(f"Unmapped MEDDOCAN annotation type: {kind}")
        start, end = int(start), int(end)
        if not 0 <= start < end <= len(text) or text[start:end] != columns[2]:
            raise ValueError("MEDDOCAN BRAT offsets disagree with the source")
        gold.append({
            "start": start, "end": end, "value": columns[2],
            "pii_type": MEDDOCAN_MAP[kind], "pii_subtype": kind,
        })
    gold.sort(key=lambda e: (e["start"], e["end"], e["pii_type"]))
    if any(a["end"] > b["start"] for a, b in zip(gold, gold[1:])):
        raise ValueError("Overlapping MEDDOCAN spans; requires manual policy")
    return gold


def prepare_meddocan(source: Path, output: Path, *, limit: int = 40) -> dict:
    """Read an already extracted Zenodo corpus; ONLY official test directories."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    ann_files = sorted(p for p in source.rglob("*.ann")
                       if any(part.lower() == "test" for part in p.parts))
    if not ann_files:
        raise ValueError("No MEDDOCAN test/*.ann files; extract meddocan.zip first")
    rows, excluded = [], []
    for ann_path in ann_files:
        txt_path = ann_path.with_suffix(".txt")
        try:
            text = txt_path.read_text(encoding="utf-8")
            entities = _meddocan_entities(text, ann_path.read_text(encoding="utf-8"))
            rows.append({
                "id": "meddocan-" + ann_path.stem,
                "profile": "meddocan_phi", "text": text,
                "entities": entities, "gold_scope": "complete",
                "gold_version": "meddocan_test_brat_coarse_v1",
                "tags": ["medical", "meddocan", "es", "test"],
                "human_reviewed": True,
            })
        except (OSError, ValueError) as exc:
            excluded.append({"file": ann_path.name, "reason": str(exc)})
    random.Random(20261103).shuffle(rows)
    selected = sorted(rows[:limit], key=lambda r: r["id"])
    return _write(output, selected, {
        "dataset": "MEDDOCAN", "task": "phi_deidentification",
        "source": "https://doi.org/10.5281/zenodo.4279323",
        "license": "CC BY 4.0",
        "split": "test_only", "source_annotations": len(ann_files),
        "eligible_documents": len(rows), "excluded": excluded,
        "sample_limit": limit, "sampling_seed": 20261103,
        "label_space": "MEDDOCAN_29_to_8_coarse_explicit_mapping",
        "not_comparable_to": ["asq_phi", "pharmaer_clinical_ner"],
    })


def _pharmaer_entities(record: dict) -> list[dict]:
    """BIO to exact character spans, with strict token/offset checks."""
    text = record["text"]
    tokens, labels, offsets = record["tokens"], record["labels"], record["start_end"]
    if not len(tokens) == len(labels) == len(offsets):
        raise ValueError("PharmaER BIO fields have different lengths")
    gold, active = [], None
    def flush() -> None:
        nonlocal active
        if active is not None:
            a, b, typ = active
            gold.append({"start": a, "end": b, "value": text[a:b],
                         "pii_type": "clinical_" + typ.lower(), "pii_subtype": typ})
        active = None
    for tok, label, offset in zip(tokens, labels, offsets):
        if len(offset) != 2 or not all(type(v) is int for v in offset):
            raise ValueError("Invalid PharmaER token offsets")
        a, b = offset
        if not 0 <= a < b <= len(text) or text[a:b] != tok:
            raise ValueError("PharmaER token offsets do not match original text")
        if label == "O":
            flush()
            continue
        match = re.fullmatch(r"([BI])-([A-Z_]+)", label)
        if not match or match[2] not in CLINICAL_TYPES:
            raise ValueError("Unexpected PharmaER BIO label")
        typ = match[2]
        if match[1] == "B":
            flush()
            active = (a, b, typ)
        elif active is None or active[2] != typ or a < active[1]:
            raise ValueError("Orphan or overlapping PharmaER I-tag")
        else:
            active = (active[0], b, typ)
    flush()
    return gold


def prepare_pharmaer(source: Path, output: Path, *, strict_test_size: bool = True) -> dict:
    """Accept a local Hugging Face test parquet or JSONL export (never train/silver)."""
    if source.suffix.lower() == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet requires: uv run --with pyarrow redact-bench ...") from exc
        records = pq.read_table(source).to_pylist()
    elif source.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    else:
        raise ValueError("PharmaER source must be test split .parquet or .jsonl")
    if strict_test_size and len(records) != 10:
        raise ValueError("PharmaER official Gold test split must contain 10 documents")
    rows = []
    for index, record in enumerate(records):
        entities = _pharmaer_entities(record)
        rows.append({
            "id": "pharmaer-" + str(record.get("document_id", index)),
            "profile": "clinical_ner", "text": record["text"], "entities": entities,
            "gold_scope": "complete", "gold_version": "pharmaer_it_gold_test_v03",
            "tags": ["medical", "clinical_ner", "it", "test", "not_pii"],
            "human_reviewed": True,
        })
    return _write(output, rows, {
        "dataset": "PharmaER.IT", "task": "clinical_entity_recognition_not_deidentification",
        "source": "https://huggingface.co/datasets/expertai/PharmaER.IT",
        "source_sha256": _digest(source.read_bytes()), "split": "gold_test_only",
        "license": "ODC-BY per dataset card; verify terms of original leaflets",
        "note": "A medical term alone is not necessarily personal data. Do not rank against PHI.",
        "label_space": "DRUG_DISEASE_SYMPTOM_ANATOMICAL_PART",
        "not_comparable_to": ["asq_phi", "meddocan_phi", "e3c_injected"],
    })
