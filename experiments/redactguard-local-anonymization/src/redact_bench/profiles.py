from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def load_profiles(path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles.yaml has no profiles mapping")
    return profiles


def build_system_prompt(profile: str, profiles_path: str | Path) -> str:
    profiles = load_profiles(profiles_path)
    if profile not in profiles:
        raise KeyError(f"Unknown RedactGuard profile: {profile}")
    definitions = profiles[profile]
    lines: list[str] = []
    for name, spec in definitions.items():
        line = f"- **{name}**: {spec.get('description', '')}"
        examples = list(spec.get("examples", []))[:3]
        if examples:
            line += "  (examples: " + ", ".join(f'"{example}"' for example in examples) + ")"
        lines.append(line)
    allowed = ", ".join(f'"{name}"' for name in definitions)
    return f"""You are a PII (Personally Identifiable Information) detection assistant.

Analyze the provided text and identify ALL instances of personally identifiable
or sensitive information. For each instance found, extract the exact text span.

## PII types to detect

{chr(10).join(lines)}

## Output format

Return a JSON object with a single key "pii_fields" containing an array.
Each element must have:
- "field_name": a short descriptive label for this specific instance
- "field_description": why this is sensitive
- "pii_type": one of [{allowed}]
- "value": the exact text span as it appears in the document
- "redacted_value": a replacement placeholder like "[REDACTED_NAME]", "[REDACTED_DATE]", etc.

## Rules

1. Extract the EXACT text span — do not paraphrase or summarize.
2. Do NOT include information that is clearly public or non-personal.
3. If no PII is found, return {{"pii_fields": []}}.
4. Return ONLY valid JSON — no explanations, no markdown code blocks.
"""
