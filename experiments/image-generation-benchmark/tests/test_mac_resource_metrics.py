from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from imagegen_bench.mac_resource_metrics import (
    read_mac_resource_summary,
    summarize_mac_samples,
)

SCRIPTS = Path(__file__).parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("mac_resource_probe", SCRIPTS / "mac_resource_probe.py")
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_vm_stat_parser_extracts_reclaimable_and_paging_counters():
    data = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free: 10.
Pages inactive: 20.
Pages speculative: 5.
Swapins: 200.
Swapouts: 100.
"""
    parsed = probe.page_counters(data)
    assert parsed["available_bytes"] == 35 * 16384
    assert parsed["swapins_pages"] == 200
    assert parsed["swapouts_pages"] == 100
    assert parsed["page_size_bytes"] == 16384


def test_swap_used_is_not_added_to_available_physical_memory():
    assert probe.swap_used_bytes(
        "vm.swapusage: total = 16.0G used = 14.0G free = 2.0G"
    ) == 14 * 1024**3
    assert probe.swap_used_bytes("vm.swapusage: unknown") is None
    samples = [
        {
            "timestamp_unix": 100.0,
            "sd_server_rss_bytes": 5 * 1024**3,
            "available_bytes": 8 * 1024**3,
            "swap_used_bytes": 14 * 1024**3,
            "page_size_bytes": 16384,
            "swapins_pages": 200,
            "swapouts_pages": 100,
        },
        {
            "timestamp_unix": 110.0,
            "sd_server_rss_bytes": 6 * 1024**3,
            "available_bytes": 7 * 1024**3,
            "swap_used_bytes": 15 * 1024**3,
            "page_size_bytes": 16384,
            "swapins_pages": 220,
            "swapouts_pages": 300,
        },
    ]
    summary = summarize_mac_samples(samples)
    assert summary["sd_server_rss_peak_bytes"] == 6 * 1024**3
    assert summary["host_reclaimable_min_bytes"] == 7 * 1024**3
    assert summary["swap_used_peak_bytes"] == 15 * 1024**3
    assert summary["swapin_delta_bytes"] == 20 * 16384
    assert summary["swapout_delta_bytes"] == 200 * 16384
    assert summary["swap_accounted_as_available_ram"] is False


def test_missing_or_reset_counters_are_unknown(tmp_path: Path):
    path = tmp_path / "memory.jsonl"
    path.write_text(
        json.dumps({
            "timestamp_unix": 100.0,
            "swapins_pages": 200, "swapouts_pages": 300,
            "page_size_bytes": 4096, "sd_server_rss_bytes": None,
        }) + "\n" + "bad-json\n" + json.dumps({
            "timestamp_unix": 110.0,
            "swapins_pages": 4, "swapouts_pages": 1,
            "page_size_bytes": 4096, "swap_used_bytes": None,
        }) + "\n"
    )
    result = read_mac_resource_summary(path)
    assert result["swapin_delta_bytes"] is None
    assert result["swapout_delta_bytes"] is None
    assert result["sd_server_rss_peak_bytes"] is None
    assert read_mac_resource_summary(tmp_path / "no-file")["samples"] == 0


def test_incomplete_vm_stat_does_not_fake_swap_counts():
    incomplete = probe.page_counters("Mach Virtual Memory Statistics:\nPages free: 50.")
    assert incomplete["available_bytes"] is None
    assert incomplete["swapins_pages"] is None
