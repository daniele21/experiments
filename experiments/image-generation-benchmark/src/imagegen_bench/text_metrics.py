from __future__ import annotations

import re
from difflib import SequenceMatcher

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value).strip().casefold())


def exact_text_match(expected: object, extracted: object) -> bool:
    return normalize_text(expected) == normalize_text(extracted)


def character_similarity(expected: object, extracted: object) -> float:
    left = normalize_text(expected)
    right = normalize_text(extracted)
    if not left and not right:
        return 1.0
    return SequenceMatcher(a=left, b=right).ratio()
