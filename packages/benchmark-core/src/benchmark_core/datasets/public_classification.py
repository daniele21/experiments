from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path


def load_banking77_categories(path: Path) -> tuple[str, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, list)
        or not payload
        or not all(isinstance(item, str) and item.strip() for item in payload)
    ):
        raise ValueError("BANKING77 categories must be a non-empty string list")
    categories = tuple(str(item) for item in payload)
    if len(categories) != len(set(categories)):
        raise ValueError("BANKING77 categories contain duplicates")
    return categories


def load_banking77_rows(path: Path) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != ["text", "category"]:
            raise ValueError(f"Unexpected BANKING77 header: {header}")
        for source_index, row in enumerate(reader):
            if len(row) != 2:
                raise ValueError(
                    f"BANKING77 row {source_index} must contain text and category"
                )
            text, category = row
            if not text.strip() or not category.strip():
                raise ValueError(
                    f"BANKING77 row {source_index} contains an empty value"
                )
            rows.append((source_index, text, category))
    if not rows:
        raise ValueError("BANKING77 split is empty")
    return rows


def load_clinc_rows(
    path: Path,
    *,
    split: str,
    exclude_terms: Iterable[str] = (),
) -> list[tuple[int, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("CLINC150 data root must be an object")

    raw = payload.get(split)
    if not isinstance(raw, list):
        raise TypeError(f"CLINC150 source has no list split {split!r}")

    normalized_exclusions = tuple(term.lower() for term in exclude_terms)
    rows: list[tuple[int, str, str]] = []
    for source_index, item in enumerate(raw):
        if not isinstance(item, list) or len(item) < 2:
            continue
        text = str(item[0]).strip()
        source_label = str(item[1]).strip()
        if not text:
            continue
        normalized = text.lower()
        if any(term in normalized for term in normalized_exclusions):
            continue
        rows.append((source_index, text, source_label))
    return rows
