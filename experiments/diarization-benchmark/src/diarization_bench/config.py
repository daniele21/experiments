from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelSpec:
    key: str
    engine: str
    family: str
    mode: str
    max_speakers: int | None
    options: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    license_note: str | None = None


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    audio: Path
    reference_rttm: Path
    tags: dict[str, Any] = field(default_factory=dict)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return payload


def load_models(path: Path) -> dict[str, ModelSpec]:
    payload = _read_yaml(path)
    raw_models = payload.get("models")
    if not isinstance(raw_models, dict) or not raw_models:
        raise ValueError(f"{path} must define a non-empty 'models' mapping")

    models: dict[str, ModelSpec] = {}
    for key, raw in raw_models.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Model {key!r} must be a mapping")
        models[key] = ModelSpec(
            key=key,
            engine=str(raw["engine"]),
            family=str(raw.get("family") or key),
            mode=str(raw.get("mode") or "offline"),
            max_speakers=raw.get("max_speakers"),
            options=dict(raw.get("options") or {}),
            tags=tuple(raw.get("tags") or ()),
            license_note=raw.get("license_note"),
        )
    return models


def load_manifest(path: Path) -> list[CaseSpec]:
    payload = _read_yaml(path)
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"{path} must define a non-empty 'cases' list")

    cases: list[CaseSpec] = []
    seen: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("Each case must be a mapping")
        case_id = str(raw["id"])
        if case_id in seen:
            raise ValueError(f"Duplicate case id: {case_id}")
        seen.add(case_id)
        cases.append(
            CaseSpec(
                case_id=case_id,
                audio=Path(str(raw["audio"])).expanduser(),
                reference_rttm=Path(str(raw["reference_rttm"])).expanduser(),
                tags=dict(raw.get("tags") or {}),
            )
        )
    return cases


def select_models(models: dict[str, ModelSpec], selector: str) -> list[ModelSpec]:
    if selector == "all":
        return list(models.values())
    keys = [item.strip() for item in selector.split(",") if item.strip()]
    unknown = [key for key in keys if key not in models]
    if unknown:
        raise ValueError(f"Unknown model(s): {', '.join(unknown)}")
    return [models[key] for key in keys]
