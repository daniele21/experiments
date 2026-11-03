"""Reproducible, non-redistributing E3C Italian benchmark preparation.

E3C's annotations are clinical entities, NOT complete PII gold. The resulting
identity-injection suite measures targeted recall/leakage only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

SOURCE_REPOSITORY = "https://github.com/hltfbk/E3C-Corpus.git"
SOURCE_VERSION = "v2.0.0"
SOURCE_SHA = "f74bdf9eaaef7f08437d0c5b930c6dbbc25bbffc"
GOLD_VERSION = "e3c_it_v2_injected_pii_v1"
SPLIT_RE = re.compile(r"(?m)^ITALIAN\s*\n([^\n]+)")
TRAIN_ID_RE = re.compile(r"IT\d{6}")
TOTAL_DOCUMENTS = 86
TRAIN_DOCUMENTS = 36
TEST_DOCUMENTS = 50

FIRST_NAMES = ("Giulia", "Elena", "Marta", "Chiara", "Sara", "Paola", "Livia")
SURNAMES = ("Vercelli", "Ferrante", "Montanari", "Rinaldi", "Fabbri", "Bellini", "Guidi")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_git(*args: str, cwd: Path | None = None) -> str:
    process = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
    )
    return process.stdout.strip()


def download_e3c(destination: Path) -> Path:
    """Fetch only Italian Layer 1 + official split, pinned to the source tag SHA."""
    destination = destination.resolve()
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        _run_git(
            "clone", "--depth", "1", "--branch", SOURCE_VERSION,
            "--filter=blob:none", "--sparse", SOURCE_REPOSITORY, str(destination),
        )
        _run_git(
            "sparse-checkout", "set", "data_collection/Italian/layer1",
            "data_annotation/Italian/layer1", "documentation", cwd=destination,
        )
    if not (destination / ".git").exists():
        raise ValueError(f"E3C source is not a Git checkout: {destination}")
    commit = _run_git("rev-parse", "HEAD", cwd=destination)
    if commit != SOURCE_SHA:
        raise ValueError(
            f"E3C checkout must be pinned to {SOURCE_VERSION}@{SOURCE_SHA}; found {commit}"
        )
    return destination


def _train_ids(source: Path) -> set[str]:
    split = (source / "documentation/train_test_split.txt").read_text(encoding="utf-8")
    match = SPLIT_RE.search(split)
    if match is None:
        raise ValueError("Official E3C split missing ITALIAN section")
    ids = TRAIN_ID_RE.findall(match.group(1))
    if len(ids) != TRAIN_DOCUMENTS or len(set(ids)) != TRAIN_DOCUMENTS:
        raise ValueError(f"Expected {TRAIN_DOCUMENTS} distinct Italian train IDs")
    return set(ids)


def _injection(source_id: str) -> tuple[str, list[dict]]:
    """Synthetic values remain stable across runs and are not asserted to be native PII."""
    number = int(source_id[2:])
    name = f"{FIRST_NAMES[number % len(FIRST_NAMES)]} {SURNAMES[(number // 7) % len(SURNAMES)]}"
    values = (
        ("private_person", name),
        ("account_number", f"RG-IT-{number:06d}"),
        ("private_email", f"paziente.it{number:06d}@example.org"),
        ("private_phone", f"+39 320 {number % 900 + 100:03d} {number % 9000 + 1000:04d}"),
        ("private_address", f"Via della Ricerca {number % 97 + 1}, Bologna"),
        ("private_date", f"{number % 27 + 1:02d}/04/1988"),
    )
    fields = (
        ("Paziente", values[0]),
        ("ID cartella", values[1]),
        ("Email", values[2]),
        ("Telefono", values[3]),
        ("Domicilio", values[4]),
        ("Data di nascita", values[5]),
    )
    lines = [f"{title}: {value}" for title, (_, value) in fields]
    block = "\n\nScheda anagrafica associata alla visita:\n" + "\n".join(lines) + "\n\n"
    entities = [
        {"pii_type": pii_type, "value": value, "pii_subtype": "synthetic_injected"}
        for pii_type, value in values
    ]
    return block, entities


def _insertion_point(text: str, ordinal: int) -> int:
    # Spread identity evidence throughout the document without changing original text.
    if ordinal % 3 == 0:
        return 0
    if ordinal % 3 == 1:
        return len(text)
    around = len(text) // 2
    right = text.find(" ", around)
    return right + 1 if right >= 0 else len(text)


def _rows(source: Path) -> tuple[list[dict], list[dict], list[dict]]:
    folder = source / "data_collection/Italian/layer1"
    annotation_folder = source / "data_annotation/Italian/layer1"
    texts = sorted(folder.glob("*.json"))
    annotations = {path.stem for path in annotation_folder.glob("*.xml")}
    ids = {path.stem for path in texts}
    if len(texts) != TOTAL_DOCUMENTS or len(ids) != TOTAL_DOCUMENTS:
        raise ValueError(f"Expected {TOTAL_DOCUMENTS} Italian Layer 1 JSON documents")
    if annotations != ids:
        raise ValueError("Italian Layer 1 XML annotation IDs do not match the JSON documents")
    train = _train_ids(source)
    if not train <= ids or len(ids - train) != TEST_DOCUMENTS:
        raise ValueError("Official Italian train/test split is inconsistent with Layer 1")

    original_rows, injected_rows, provenance = [], [], []
    for ordinal, path in enumerate(p for p in texts if p.stem not in train):
        raw_bytes = path.read_bytes()
        document = json.loads(raw_bytes)
        source_id = path.stem
        if document.get("id") != source_id or document.get("language") != "it":
            raise ValueError(f"Invalid E3C Italian document metadata: {source_id}")
        text = document.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"E3C source has no clinical narrative: {source_id}")
        family_id = f"e3c-it-{source_id}"
        original_rows.append({
            "id": f"e3c-context-{source_id}", "source_id": source_id,
            "profile": "healthcare", "text": text, "entities": [],
            "tags": ["e3c", "italian", "clinical_context", "unlabeled"],
            "content_family_id": family_id, "variant_id": "context",
            "gold_version": "e3c_it_v2_context_unlabeled",
            "gold_scope": "unlabeled", "human_reviewed": False,
        })
        block, entities = _injection(source_id)
        position = _insertion_point(text, ordinal)
        augmented = text[:position] + block + text[position:]
        for entity in entities:
            local_start = block.index(entity["value"])
            entity["start"] = position + local_start
            entity["end"] = entity["start"] + len(entity["value"])
            if augmented[entity["start"]:entity["end"]] != entity["value"]:
                raise ValueError(f"Invalid injection offsets: {source_id}")
        injected_rows.append({
            "id": f"e3c-injected-{source_id}", "source_id": source_id,
            "profile": "healthcare", "text": augmented, "entities": entities,
            "tags": ["e3c", "italian", "clinical_context", "synthetic", "injected_pii"],
            "content_family_id": family_id, "variant_id": "injected",
            "gold_version": GOLD_VERSION, "gold_scope": "injected_only",
            "human_reviewed": False,
        })
        provenance.append({
            "source_id": source_id, "original_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "original_text_sha256": _sha(text),
            "injected_text_sha256": _sha(augmented),
            "injection_position": position, "injected_entity_count": len(entities),
        })
    if len(original_rows) != TEST_DOCUMENTS or len(injected_rows) != TEST_DOCUMENTS:
        raise ValueError("E3C Layer 1 test must contain exactly 50 documents")
    return original_rows, injected_rows, provenance


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def prepare_e3c(source: Path, output_dir: Path) -> dict:
    """Create two separate provenance-pinned tracks; no upstream text is committed."""
    context, injected, provenance = _rows(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "clinical_context.jsonl", context)
    _write_jsonl(output_dir / "synthetic_pii.jsonl", injected)
    manifest = {
        "dataset": "E3C Italian Layer 1", "source_repository": SOURCE_REPOSITORY,
        "source_tag": SOURCE_VERSION, "source_sha": SOURCE_SHA,
        "source_license": "CC BY-NC", "official_train_documents": TRAIN_DOCUMENTS,
        "official_test_documents": TEST_DOCUMENTS, "split": "test",
        "clinical_context": {
            "file": "clinical_context.jsonl", "documents": TEST_DOCUMENTS,
            "gold_scope": "unlabeled", "scoring": "not_permitted",
        },
        "synthetic_pii": {
            "file": "synthetic_pii.jsonl", "documents": TEST_DOCUMENTS,
            "gold_version": GOLD_VERSION, "gold_scope": "injected_only",
            "scoring": "targeted_recall_and_leakage_only",
            "entities_per_document": 6, "human_reviewed": False,
        },
        "test_sources": provenance,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
