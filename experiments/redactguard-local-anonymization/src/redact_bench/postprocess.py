from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from redact_bench.models import Finding


@dataclass(frozen=True)
class ResolutionResult:
    findings: list[Finding]
    resolved_items: int
    unresolved_items: int


def _normalized_pattern(value: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in value.split() if part]
    if not parts:
        return re.compile(r"(?!x)x")
    return re.compile(r"\s+".join(parts))


def resolve_model_payload(text: str, payload: dict[str, Any]) -> ResolutionResult:
    """Resolve model-proposed values to deterministic source spans.

    The model proposes values; deterministic code maps every occurrence back to
    the source. Model items that cannot be mapped remain explicit diagnostics
    instead of disappearing from benchmark evidence.
    """
    fields = payload.get("pii_fields", [])
    if not isinstance(fields, list):
        raise TypeError("response JSON has no pii_fields array")

    findings: list[Finding] = []
    seen: set[tuple[int, int, str]] = set()
    resolved_items = 0
    unresolved_items = 0

    for field in fields:
        if not isinstance(field, dict):
            unresolved_items += 1
            continue
        value = str(field.get("value") or "").strip()
        pii_type = str(field.get("pii_type") or "").strip()
        if not value or not pii_type:
            unresolved_items += 1
            continue

        item_resolved = False
        for match in _normalized_pattern(value).finditer(text):
            item_resolved = True
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

        if item_resolved:
            resolved_items += 1
        else:
            unresolved_items += 1

    return ResolutionResult(
        findings=sorted(findings, key=lambda finding: (finding.start, finding.end, finding.pii_type)),
        resolved_items=resolved_items,
        unresolved_items=unresolved_items,
    )


def findings_from_model_payload(text: str, payload: dict[str, Any]) -> list[Finding]:
    """Backward-compatible findings-only wrapper."""
    return resolve_model_payload(text, payload).findings
