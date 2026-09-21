from __future__ import annotations

import re
from typing import Any

from redact_bench.models import Finding


def _normalized_pattern(value: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in value.split() if part]
    if not parts:
        return re.compile(r"(?!x)x")
    return re.compile(r"\s+".join(parts))


def findings_from_model_payload(text: str, payload: dict[str, Any]) -> list[Finding]:
    """Apply the RedactGuard v1 value-to-span contract.

    The model proposes exact values; deterministic code finds every occurrence
    of each proposed value in the source text. Hallucinated values produce no
    finding and are tracked at the raw-output layer rather than redacted.
    """
    fields = payload.get("pii_fields", [])
    if not isinstance(fields, list):
        raise TypeError("response JSON has no pii_fields array")

    findings: list[Finding] = []
    seen: set[tuple[int, int, str]] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        value = str(field.get("value") or "").strip()
        pii_type = str(field.get("pii_type") or "unknown")
        if not value:
            continue
        for match in _normalized_pattern(value).finditer(text):
            key = (match.start(), match.end(), pii_type)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    pii_type=pii_type,
                    value=text[match.start() : match.end()],
                    start=match.start(),
                    end=match.end(),
                    field_name=str(field.get("field_name") or ""),
                    field_description=str(field.get("field_description") or ""),
                )
            )
    return sorted(findings, key=lambda f: (f.start, f.end, f.pii_type))
