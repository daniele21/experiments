from __future__ import annotations

from model_capability_bench.analytics.pareto import (
    build_frontier_payload,
    pareto_flags,
)


def test_pareto_flags_mark_dominated_points() -> None:
    points = [
        {"model_signature": "a", "size": 4.0, "quality": 80.0},
        {"model_signature": "b", "size": 5.0, "quality": 82.0},
        {"model_signature": "c", "size": 6.0, "quality": 81.0},
    ]

    flags = pareto_flags(points, x_key="size", y_key="quality")

    assert flags == {"a": True, "b": True, "c": False}


def test_frontier_payload_groups_family_and_compression() -> None:
    payload = build_frontier_payload(
        [
            {
                "model_key": "m-q4",
                "model_signature": "q4",
                "family": "family",
                "parameters_b": 4.0,
                "quantization": "Q4_K_M",
                "artifact_size_bytes": 2_000_000_000,
                "overall_quality_score": 80.0,
                "latency_p50_ms": 100.0,
                "deployment": "local",
                "resource_summary": {"process_rss_bytes_peak": 3_000_000_000},
            },
            {
                "model_key": "m-q8",
                "model_signature": "q8",
                "family": "family",
                "parameters_b": 4.0,
                "quantization": "Q8_0",
                "artifact_size_bytes": 4_000_000_000,
                "overall_quality_score": 82.0,
                "latency_p50_ms": 120.0,
                "deployment": "local",
                "resource_summary": {"process_rss_bytes_peak": 5_000_000_000},
            },
        ]
    )

    assert payload["compression_groups"] == ["family:4b"]
    assert {point["family"] for point in payload["points"]} == {"family"}
