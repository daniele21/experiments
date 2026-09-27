from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from benchmark_core.pricing import (
    TokenPrices,
    estimate_token_cost_usd,
    load_pricing_snapshot,
    pricing_snapshot_metadata,
)

PRICING_FILE = Path(__file__).resolve().parents[2] / "pricing_snapshot.json"


@lru_cache(maxsize=1)
def load_pricing() -> dict[str, Any]:
    """Compatibility wrapper around the shared pricing snapshot loader."""
    return load_pricing_snapshot(PRICING_FILE)


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

    price = load_pricing()["prices_per_million_tokens"][key]
    return estimate_token_cost_usd(
        TokenPrices(
            input_per_million=float(price["input"]),
            cached_input_per_million=float(
                price.get("cached_input", price["input"])
            ),
            output_per_million=float(price["output"]),
        ),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
    )


def pricing_metadata() -> dict[str, Any]:
    return pricing_snapshot_metadata(load_pricing())
