from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PRICING_FILE = Path(__file__).resolve().parents[2] / "pricing_snapshot.json"


@lru_cache(maxsize=1)
def load_pricing() -> dict[str, Any]:
    return json.loads(PRICING_FILE.read_text(encoding="utf-8"))


def _price_key(provider: str, model: str) -> str | None:
    pricing = load_pricing()["prices_per_million_tokens"]
    if provider == "jev" and model.startswith("jev"):
        return "jev"
    if model in pricing:
        return model
    return None


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = None,
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None

    key = _price_key(provider, model)
    if key is None:
        return None

    prices = load_pricing()["prices_per_million_tokens"][key]
    input_total = int(input_tokens or 0)
    cached = min(int(cached_input_tokens or 0), input_total)
    uncached = input_total - cached
    output = int(output_tokens or 0)

    return (
        uncached * float(prices["input"])
        + cached * float(prices.get("cached_input", prices["input"]))
        + output * float(prices["output"])
    ) / 1_000_000


def pricing_metadata() -> dict[str, Any]:
    pricing = load_pricing()
    return {
        "currency": pricing["currency"],
        "as_of": pricing["as_of"],
        "processing": pricing["processing"],
        "prices_per_million_tokens": pricing["prices_per_million_tokens"],
        "notes": pricing["notes"],
    }
