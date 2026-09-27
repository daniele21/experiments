from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def append_jsonl_record(record: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        to_jsonable(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with output.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")
        handle.flush()


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise TypeError(
                    f"JSONL record {line_number} in {path} must be an object"
                )
            records.append(payload)
    return records


def iter_jsonl_records(path: Path) -> Iterable[dict[str, Any]]:
    yield from read_jsonl_records(path)
