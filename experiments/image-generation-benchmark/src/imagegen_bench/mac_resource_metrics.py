"""Read-only telemetry reduction for a Mac image-generation benchmark.

Never call used swap a RAM capacity credit. Counters are cumulative and their
first/last difference represents sampled paging over the benchmark window.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summarize_mac_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "samples": len(samples),
        "rss_scope": "owned_sd_server_process_only_not_unified_memory",
        "swap_accounted_as_available_ram": False,
    }
    if not samples:
        return result

    def collected(key: str) -> list[int]:
        return [
            int(row[key]) for row in samples
            if isinstance(row.get(key), (int, float))
            and not isinstance(row[key], bool)
            and int(row[key]) >= 0
        ]

    for key, summary_key, reduce in (
        ("sd_server_rss_bytes", "sd_server_rss_peak_bytes", max),
        ("swap_used_bytes", "swap_used_peak_bytes", max),
        ("available_bytes", "host_reclaimable_min_bytes", min),
    ):
        values = collected(key)
        result[summary_key] = reduce(values) if values else None

    for key in ("swap_used_bytes", "available_bytes"):
        values = collected(key)
        result[f"{key}_start"] = values[0] if values else None
        result[f"{key}_end"] = values[-1] if values else None

    for key, name in (("swapins_pages", "swapin"), ("swapouts_pages", "swapout")):
        points = [
            row for row in samples
            if isinstance(row.get(key), int)
            and isinstance(row.get("page_size_bytes"), int)
            and row["page_size_bytes"] > 0
        ]
        if (len(points) < 2 or
                points[0]["page_size_bytes"] != points[-1]["page_size_bytes"]):
            result[f"{name}_delta_bytes"] = None
            continue
        pages = points[-1][key] - points[0][key]
        result[f"{name}_delta_bytes"] = (
            pages * points[0]["page_size_bytes"] if pages >= 0 else None
        )

    timestamps = collected("timestamp_unix")
    if len(timestamps) >= 2:
        result["sampling_span_seconds"] = round(timestamps[-1] - timestamps[0], 2)
    else:
        result["sampling_span_seconds"] = None
    return result


def read_mac_resource_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return summarize_mac_samples([])
    data: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            data.append(row)
    return summarize_mac_samples(data)
