from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TokenPrices:
    input_per_million: float
    output_per_million: float
    cached_input_per_million: float | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("input_per_million", self.input_per_million),
            ("output_per_million", self.output_per_million),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if self.cached_input_per_million is not None and self.cached_input_per_million < 0:
            raise ValueError("cached_input_per_million must be >= 0")


def estimate_token_cost_usd(
    prices: TokenPrices,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = None,
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None

    input_total = int(input_tokens or 0)
    output_total = int(output_tokens or 0)
    cached = min(max(int(cached_input_tokens or 0), 0), max(input_total, 0))
    uncached = max(input_total, 0) - cached
    cached_price = (
        prices.cached_input_per_million
        if prices.cached_input_per_million is not None
        else prices.input_per_million
    )

    return (
        uncached * prices.input_per_million
        + cached * cached_price
        + max(output_total, 0) * prices.output_per_million
    ) / 1_000_000


def load_pricing_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Pricing snapshot must be a JSON object: {path}")
    return payload


def pricing_snapshot_metadata(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "currency",
        "as_of",
        "processing",
        "prices_per_million_tokens",
        "notes",
    )
    return {key: snapshot[key] for key in keys if key in snapshot}
