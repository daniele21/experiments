from __future__ import annotations

import html
import json
from typing import Any


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def format_value(value: Any, precision: int) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{precision}f}".rstrip("0").rstrip(".")
    return str(value)


def json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    )
