from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DETECTION_CONTRACT_VERSION = "redactguard-detection-v2"


@lru_cache(maxsize=4)
def load_profile_snapshot(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("profiles.yaml must contain a mapping")
    return payload


def load_contract_metadata(path: str | Path) -> dict[str, Any]:
    source = load_profile_snapshot(path).get("source", {})
    if not isinstance(source, dict):
        raise ValueError("profiles.yaml source metadata must be a mapping")
    return dict(source)


def contract_snapshot_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_profiles(path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    payload = load_profile_snapshot(path)
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles.yaml has no profiles mapping")
    return profiles


def build_system_prompt(profile: str, profiles_path: str | Path) -> str:
    profiles = load_profiles(profiles_path)
    if profile not in profiles:
        raise KeyError(f"Unknown RedactGuard profile: {profile}")
    definitions = profiles[profile]
    snapshot = load_profile_snapshot(profiles_path)
    meta = snapshot.get("profiles_meta", {}).get(profile, {})
    task_type = meta.get("task_type")
    if not task_type:
        if profile.endswith("_clinical_ner") or profile == "clinical_ner":
            task_type = "clinical_ner"
        else:
            task_type = "pii_redaction"

    lines: list[str] = []
    for name, spec in definitions.items():
        line = f"- **{name}**: {spec.get('description', '')}"
        examples = list(spec.get("examples", []))[:3]
        if examples:
            line += "  (examples: " + ", ".join(f'"{example}"' for example in examples) + ")"
        lines.append(line)
    allowed = ", ".join(f'"{name}"' for name in definitions)

    if task_type == "clinical_ner":
        return f"""You are an expert Clinical and Biomedical Named Entity Recognition (NER) assistant.

Detection contract: {DETECTION_CONTRACT_VERSION}

Analyze the provided clinical text and identify ALL instances of medical entities,
findings, diagnoses, clinical procedures, chemical substances, and proteins that match
the active type definitions below.

## Clinical entity types to detect

{chr(10).join(lines)}

## Output format

Return a JSON object with a single key "pii_fields" containing an array.
Each element must contain:
- "pii_type": one of [{allowed}]
- "value": the exact text span as it appears in the document

Example:
{{"pii_fields":[{{"pii_type":"clinical_disease","value":"diabetes mellitus"}}]}}

## Rules

1. Extract the EXACT text span — do not paraphrase, normalize, or summarize it.
2. Follow the active type definitions. Do not invent new types.
3. Extract EVERY medical entity comprehensively, even when describing generic medical concepts,
   symptoms, treatments, or laboratory findings without an identifiable patient.
4. If no clinical entities matching the active types are found, return {{"pii_fields":[]}}.
5. Return ONLY valid JSON — no explanations and no markdown code blocks.
"""

    return f"""You are a PII (Personally Identifiable Information) detection assistant.

Detection contract: {DETECTION_CONTRACT_VERSION}

Analyze the provided text and identify ALL instances of personally identifiable
or sensitive information that match the active type definitions below.

## PII types to detect

{chr(10).join(lines)}

## Output format

Return a JSON object with a single key "pii_fields" containing an array.
Each element must contain:
- "pii_type": one of [{allowed}]
- "value": the exact text span as it appears in the document

Example:
{{"pii_fields":[{{"pii_type":"private_person","value":"Mario Rossi"}}]}}

## Rules

1. Extract the EXACT text span — do not paraphrase, normalize, or summarize it.
2. Follow the active type definitions. Do not invent new PII types.
3. Do NOT include information that is clearly public or non-personal unless the
   active type definition explicitly classifies it as sensitive in context.
4. If no PII is found, return {{"pii_fields":[]}}.
5. Return ONLY valid JSON — no explanations and no markdown code blocks.
"""
