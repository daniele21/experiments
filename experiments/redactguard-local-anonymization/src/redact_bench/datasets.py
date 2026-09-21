from __future__ import annotations

import json
from pathlib import Path

from redact_bench.models import Case, Span


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
            raise ValueError(f"Gold entity {value!r} not present in case text")
    unique = {(s.start, s.end, s.pii_type): s for s in spans}
    return tuple(sorted(unique.values(), key=lambda s: (s.start, s.end, s.pii_type)))


def load_jsonl(path: str | Path) -> list[Case]:
    cases: list[Case] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            text = str(row["text"])
            cases.append(
                Case(
                    case_id=str(row["id"]),
                    profile=str(row["profile"]),
                    text=text,
                    gold=_resolve_entities(text, list(row.get("entities", []))),
                    tags=tuple(str(x) for x in row.get("tags", [])),
                )
            )
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Dataset contains duplicate case ids")
    return cases



def load_dataset(path: str | Path) -> list[Case]:
    """Load either the committed JSONL format or a realistic dataset directory."""
    dataset_path = Path(path)
    if dataset_path.is_dir():
        from redact_bench.realistic_dataset import load_realistic_dataset

        return load_realistic_dataset(dataset_path)
    return load_jsonl(dataset_path)
