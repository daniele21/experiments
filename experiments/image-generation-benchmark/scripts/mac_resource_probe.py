"""Mac resource telemetry for Experiments image benchmarks.

Samples host swap/page activity and owned native sd-server process RSS.
These are *not* GPU or whole-system unified-memory peaks.
No model files, credentials or prompts are read.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

_GIB = 1024**3


def command(*args: str) -> str | None:
    try:
        value = subprocess.run(
            args, check=True, capture_output=True, text=True, timeout=3,
        )
        return value.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def page_counters(raw: str | None) -> dict[str, int | None]:
    counters: dict[str, int | None] = {
        "page_size_bytes": None,
        "available_bytes": None,
        "swapins_pages": None,
        "swapouts_pages": None,
    }
    if raw is None:
        return counters
    match = re.search(r"page size of\s+(\d+)\s+bytes", raw)
    if not match:
        return counters
    page_size = int(match.group(1))
    if page_size < 1:
        return counters
    parsed = {}
    for line in raw.splitlines():
        key, _, value = line.partition(":")
        if not value:
            continue
        stripped = value.strip().rstrip(".")
        if stripped.isdigit():
            parsed[key.strip().lower()] = int(stripped)
    counters["page_size_bytes"] = page_size
    needed = ["pages free", "pages inactive", "pages speculative"]
    if all(k in parsed for k in needed):
        counters["available_bytes"] = sum(parsed[k] for k in needed) * page_size
    counters["swapins_pages"] = parsed.get("swapins")
    counters["swapouts_pages"] = parsed.get("swapouts")
    return counters


def swap_used_bytes(raw: str | None) -> int | None:
    if raw is None:
        return None
    match = re.search(r"\bused\s*=\s*(\d+(?:\.\d+)?)\s*([KMGT])B?\b", raw, re.I)
    if not match:
        return None
    number = float(match.group(1))
    if not math.isfinite(number) or number < 0:
        return None
    return int(number * 1024 ** {"K": 1, "M": 2, "G": 3, "T": 4}[match.group(2).upper()])


def native_process_rss_bytes(port: int) -> int | None:
    """Identify only the loopback listener; missing RSS is unknown, never zero."""
    listeners = command(
        "lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN",
    )
    if not listeners:
        return None
    for line in listeners.splitlines():
        if not line.isdigit():
            continue
        rss = command("ps", "-o", "rss=", "-p", line)
        if rss and rss.strip().isdigit():
            return int(rss.strip()) * 1024
    return None


def sample(port: int) -> dict[str, int | float | None]:
    details = page_counters(command("vm_stat"))
    return {
        "timestamp_unix": round(time.time(), 3),
        "sd_server_rss_bytes": native_process_rss_bytes(port),
        "swap_used_bytes": swap_used_bytes(command("sysctl", "vm.swapusage")),
        **details,
    }


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "samples": len(samples),
        "rss_scope": "owned_sd_server_process_only_not_unified_memory",
        "swap_accounted_as_available_ram": False,
    }
    if not samples:
        return result
    def collected(key: str) -> list[int]:
        return [int(row[key]) for row in samples
                if isinstance(row.get(key), (int, float)) and not isinstance(row[key], bool)
                and int(row[key]) >= 0]
    for key, prefix, aggregate in (
        ("sd_server_rss_bytes", "sd_server_rss", max),
        ("swap_used_bytes", "swap_used", max),
        ("available_bytes", "host_reclaimable", min),
    ):
        values = collected(key)
        result[f"{prefix}_{'min' if aggregate is min else 'peak'}_bytes"] = (
            aggregate(values) if values else None
        )
    first, last = samples[0], samples[-1]
    for key in ("swap_used_bytes", "available_bytes"):
        result[f"{key}_start"] = first.get(key)
        result[f"{key}_end"] = last.get(key)
    for key, name in (("swapins_pages", "swapin"), ("swapouts_pages", "swapout")):
        points = [
            row for row in samples if isinstance(row.get(key), int)
            and isinstance(row.get("page_size_bytes"), int)
            and row["page_size_bytes"] > 0
        ]
        if len(points) < 2:
            result[f"{name}_delta_bytes"] = None
            continue
        if points[-1]["page_size_bytes"] != points[0]["page_size_bytes"]:
            result[f"{name}_delta_bytes"] = None
            continue
        page_delta = points[-1][key] - points[0][key]
        result[f"{name}_delta_bytes"] = (
            page_delta * points[0]["page_size_bytes"] if page_delta >= 0 else None
        )
    result["sampling_span_seconds"] = round(
        float(last["timestamp_unix"]) - float(first["timestamp_unix"]), 2,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.interval <= 60:
        parser.error("invalid port or sampling interval")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    active = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal active
        active = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with args.output.open("a", encoding="utf-8", buffering=1) as out:
        while active:
            try:
                out.write(json.dumps(sample(args.port)) + "\n")
            except Exception:
                # Sampling must never terminate the owner of the generation.
                out.write(json.dumps({"timestamp_unix": time.time(),
                                      "telemetry_error": "observation_unavailable"}) + "\n")
            if active:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
