from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from typing import Any


def seeded_random(seed: int) -> random.Random:
    """Return an isolated deterministic RNG for benchmark selection."""
    return random.Random(seed)


def fingerprint_values(values: Sequence[Any]) -> str:
    """Create a stable SHA-256 fingerprint for an ordered benchmark selection."""
    payload = json.dumps(
        list(values),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
