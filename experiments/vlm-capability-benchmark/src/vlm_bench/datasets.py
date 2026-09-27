from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from vlm_bench.evaluators import BoundingBox


class DatasetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetCase:
    sample_id: str
    task: str
    asset_path: Path
    question: str
    expected: Any
    target_label: str | None = None
    target_box: BoundingBox | None = None


def _require_text(payload: dict[str, Any], key: str, sample_id: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DatasetValidationError(f"{sample_id}: {key} must be non-empty text")
    return value


def load_dataset_cases(
    path: str | Path,
    *,
    require_assets: bool = True,
) -> tuple[DatasetCase, ...]:
    dataset_path = Path(path)
    payload = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise DatasetValidationError("dataset root must contain a cases list")

    seen: set[str] = set()
    cases: list[DatasetCase] = []
    for index, raw_case in enumerate(payload["cases"]):
        if not isinstance(raw_case, dict):
            raise DatasetValidationError(f"case {index} must be a mapping")
        sample_id = _require_text(raw_case, "sample_id", f"case-{index}")
        if sample_id in seen:
            raise DatasetValidationError(f"duplicate sample_id: {sample_id}")
        seen.add(sample_id)

        relative_asset = _require_text(raw_case, "asset", sample_id)
        asset_path = (dataset_path.parent / relative_asset).resolve()
        if require_assets and not asset_path.is_file():
            raise DatasetValidationError(f"{sample_id}: asset not found: {relative_asset}")

        target_box = None
        raw_box = raw_case.get("target_box")
        if raw_box is not None:
            if not isinstance(raw_box, list) or len(raw_box) != 4:
                raise DatasetValidationError(f"{sample_id}: target_box must contain 4 values")
            try:
                target_box = BoundingBox(*(float(value) for value in raw_box))
            except (TypeError, ValueError) as exc:
                raise DatasetValidationError(f"{sample_id}: invalid target_box") from exc

        cases.append(
            DatasetCase(
                sample_id=sample_id,
                task=_require_text(raw_case, "task", sample_id),
                asset_path=asset_path,
                question=_require_text(raw_case, "question", sample_id),
                expected=raw_case.get("expected"),
                target_label=raw_case.get("target_label"),
                target_box=target_box,
            )
        )

    return tuple(cases)
