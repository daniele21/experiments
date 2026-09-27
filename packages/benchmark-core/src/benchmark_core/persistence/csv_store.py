from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any


def _serialize_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Real) and not isinstance(value, bool):
        try:
            if math.isnan(float(value)):
                return ""
        except (TypeError, ValueError):
            pass
    return value


def _merge_fieldnames(
    existing: Sequence[str],
    requested: Sequence[str],
    records: Sequence[Mapping[str, Any]],
) -> list[str]:
    fields = list(existing)
    for field in requested:
        if field not in fields:
            fields.append(field)
    for record in records:
        for field in record:
            if field not in fields:
                fields.append(field)
    return fields


def append_csv_records(
    records: Sequence[Mapping[str, Any]],
    output: Path,
    *,
    fieldnames: Sequence[str] = (),
) -> None:
    """Append logical records while preserving a stable union CSV schema.

    The file is rewritten atomically at the logical level so newly introduced fields can
    be added without dropping older rows, matching the current benchmark append contract.
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    existing_rows: list[dict[str, Any]] = []
    existing_fields: list[str] = []
    if output.exists():
        with output.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            existing_fields = list(reader.fieldnames or [])
            existing_rows = [dict(row) for row in reader]

    fields = _merge_fieldnames(existing_fields, fieldnames, records)
    if not fields:
        return

    rows = [*existing_rows, *records]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialize_value(row.get(field)) for field in fields})
