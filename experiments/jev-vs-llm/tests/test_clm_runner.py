from __future__ import annotations

import pandas as pd
import pytest

from scripts.clm_manager import CLMEndpoint, normalize_clm_base_url
from scripts.run_clm_matrix import _experiments, _models, _summary


def test_normalize_clm_base_url_accepts_root_or_v1_suffix():
    assert normalize_clm_base_url("http://127.0.0.1:8700/") == "http://127.0.0.1:8700"
    assert normalize_clm_base_url("http://127.0.0.1:8700/v1") == "http://127.0.0.1:8700"


def test_clm_preflight_requires_requested_model_and_healthy_embedder(monkeypatch):
    endpoint = CLMEndpoint("http://clm.test")

    def fake_get(path, *, timeout=None):
        if path == "/health":
            return {"ok": True, "embedder": True, "mock": False}
        assert path == "/v1/models"
        return {"models": [{"name": "clm-latest"}, {"name": "clm-raw"}]}

    monkeypatch.setattr(endpoint, "_get", fake_get)

    status = endpoint.preflight(["clm-latest"])

    assert status["served_models"] == ["clm-latest", "clm-raw"]
    assert status["embedder_healthy"] is True
    assert status["mock"] is False


def test_clm_preflight_rejects_unserved_checkpoint(monkeypatch):
    endpoint = CLMEndpoint("http://clm.test")
    monkeypatch.setattr(
        endpoint,
        "_get",
        lambda path, **kwargs: (
            {"ok": True, "embedder": True}
            if path == "/health"
            else {"models": [{"name": "clm-latest"}]}
        ),
    )

    with pytest.raises(RuntimeError, match="not served"):
        endpoint.preflight(["missing-checkpoint"])


def test_public_all_maps_to_routing_and_calibration_only():
    assert _experiments("all", "public") == ["routing", "calibration"]


def test_public_runner_rejects_smoke_only_experiment():
    with pytest.raises(ValueError, match="only routing and calibration"):
        _experiments("routing,scaling", "public")


def test_model_parser_deduplicates_preserving_order():
    assert _models("clm-latest,clm-raw,clm-latest") == ["clm-latest", "clm-raw"]


def test_summary_uses_same_row_metrics_as_local_runner():
    frame = pd.DataFrame(
        [
            {"valid": True, "correct": True, "latency_ms": 10.0},
            {"valid": True, "correct": False, "latency_ms": 30.0},
        ]
    )

    summary = _summary(frame, model="clm-latest", experiment="routing", elapsed_s=1.2)

    assert summary["valid_cases"] == 2
    assert summary["total_cases"] == 2
    assert summary["accuracy_pct"] == 50.0
    assert summary["avg_latency_ms"] == 20.0
