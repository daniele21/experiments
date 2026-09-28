from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when benchmark configuration cannot be resolved safely."""


def load_yaml_mapping(
    path: Path,
    *,
    required: bool = False,
) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise ConfigError(f"Configuration file not found: {path}")
        return {}

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ConfigError(f"Expected a YAML mapping in {path}")
    return {str(key): value for key, value in payload.items()}


def load_yaml_section(
    path: Path,
    section: str,
    *,
    required: bool = False,
) -> dict[str, Any]:
    payload = load_yaml_mapping(path, required=required)
    value = payload.get(section)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"Expected section {section!r} in {path} to be a mapping")
    return {str(key): item for key, item in value.items()}


def parse_csv_selection(
    value: str,
    *,
    available: Sequence[str] = (),
    all_token: str = "all",
) -> list[str]:
    raw = value.strip()
    if raw.lower() == all_token.lower():
        selected = list(available)
    else:
        selected = [item.strip() for item in raw.split(",") if item.strip()]

    unique = list(dict.fromkeys(selected))
    if not unique:
        raise ConfigError("At least one value is required")
    return unique
