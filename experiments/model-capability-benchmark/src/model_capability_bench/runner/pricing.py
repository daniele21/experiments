from __future__ import annotations

import dataclasses
from functools import cache
from pathlib import Path
from typing import Any

from benchmark_core import (
    InferenceResult,
    ResolvedModel,
    TokenPrices,
    estimate_token_cost_usd,
    load_pricing_snapshot,
    pricing_snapshot_metadata,
)


@cache
def load_benchmark_pricing(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return load_pricing_snapshot(path)


def _price_entry(
    snapshot: dict[str, Any],
    model: ResolvedModel,
) -> dict[str, Any] | None:
    raw = snapshot.get("prices_per_million_tokens")
    if not isinstance(raw, dict):
        return None

    candidates = [
        c for c in (
            model.model.model_key,
            model.model.model_id,
            model.effective_model_id,
        )
        if c
    ]
    for candidate in candidates:
        entry = raw.get(candidate)
        if isinstance(entry, dict) and str(entry.get("match") or "exact") == "exact":
            return entry

    for price_key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        match_type = str(entry.get("match") or "")
        if match_type == "prefix":
            for candidate in candidates:
                if str(candidate).startswith(str(price_key)):
                    return entry
        elif (
            match_type == "provider"
            and str(price_key) == str(model.provider.provider_key)
        ):
            return entry
    return None


def enrich_inference_cost(
    *,
    pricing_path: Path,
    model: ResolvedModel,
    result: InferenceResult,
) -> InferenceResult:
    if result.estimated_cost_usd is not None:
        return result

    snapshot = load_benchmark_pricing(pricing_path.resolve())
    entry = _price_entry(snapshot, model)
    if entry is None:
        return result

    try:
        prices = TokenPrices(
            input_per_million=float(entry["input"]),
            cached_input_per_million=float(
                entry.get("cached_input", entry["input"])
            ),
            output_per_million=float(entry["output"]),
        )
    except (KeyError, TypeError, ValueError):
        return result

    cost = estimate_token_cost_usd(
        prices,
        input_tokens=result.usage.input_tokens,
        cached_input_tokens=result.usage.cached_input_tokens,
        output_tokens=result.usage.output_tokens,
    )
    if cost is None:
        return result

    metadata = dict(result.metadata)
    metadata["pricing"] = {
        **pricing_snapshot_metadata(snapshot),
        "price_key": model.model.model_key,
        "source": entry.get("source"),
        "source_url": entry.get("source_url"),
    }
    return dataclasses.replace(
        result,
        estimated_cost_usd=cost,
        metadata=metadata,
    )
