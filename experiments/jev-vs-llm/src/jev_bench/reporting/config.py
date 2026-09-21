"""Reporting configuration loader and helper functions."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parent / "reporting_config.yaml"

_DEFAULT_CONFIG: dict[str, Any] = {
    "theme": {
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "colors": {
            "primary": "#0f172a",
            "primary_hover": "#1e293b",
            "accent": "#4f46e5",
            "accent_light": "#e0e7ff",
            "success": "#059669",
            "success_bg": "#ecfdf5",
            "warning": "#d97706",
            "warning_bg": "#fffbeb",
            "danger": "#dc2626",
            "danger_bg": "#fef2f2",
            "neutral_bg": "#f8fafc",
            "surface": "#ffffff",
            "surface_alt": "#f1f5f9",
            "border": "#e2e8f0",
            "border_dark": "#cbd5e1",
            "text": "#0f172a",
            "text_muted": "#64748b",
            "text_light": "#94a3b8",
        },
        "chart_palette": [
            "#4f46e5",
            "#059669",
            "#d97706",
            "#7c3aed",
            "#0284c7",
            "#e11d48",
            "#0d9488",
            "#ea580c",
            "#475569",
        ],
    },
    "experiments": {
        "routing": {
            "id": "routing",
            "title": "Routing",
            "full_title": "Routing & Intent Classification",
            "tag": "01-routing",
            "public_tag": "01-routing-public",
            "description": "Multi-way intent classification evaluated on client queries.",
            "cli_command": "uv run python scripts/run_local_matrix.py --experiments routing --dataset public",
        },
        "calibration": {
            "id": "calibration",
            "title": "Calibration",
            "full_title": "Confidence & Probability Calibration",
            "tag": "02-calibration",
            "public_tag": "02-calibration-public",
            "description": "Confidence vs probability calibration, ECE, and selective automation.",
            "cli_command": "uv run python scripts/run_local_matrix.py --experiments calibration --dataset public",
        },
        "scaling": {
            "id": "scaling",
            "title": "Scaling",
            "full_title": "Parallel Decision Scaling",
            "tag": "03-parallel-scaling",
            "public_tag": "03-parallel-scaling",
            "description": "Throughput and latency scaling from 1 to 32 parallel decisions.",
            "cli_command": "uv run python scripts/run_local_matrix.py --experiments scaling",
        },
        "workflow": {
            "id": "workflow",
            "title": "Workflow",
            "full_title": "Deterministic Workflow Execution",
            "tag": "04-workflow",
            "public_tag": "04-workflow",
            "description": "Deterministic DAG routing vs monolithic policy prompt execution.",
            "cli_command": "uv run python scripts/run_local_matrix.py --experiments workflow",
        },
        "agent": {
            "id": "agent",
            "title": "Agent",
            "full_title": "Hybrid Agent Decision Layer",
            "tag": "05-hybrid-agent",
            "public_tag": "05-hybrid-agent",
            "description": "Decision-layer speed and accuracy before generative steps.",
            "cli_command": "uv run python scripts/run_local_matrix.py --experiments agent",
        },
    },
    "model_labels": {
        "qwen3.5-4b-q4km": "Korgis · Qwen3.5 4B Q4_K_M",
        "minicpm3-4b-q4km": "Korgis · MiniCPM3 4B Q4_K_M",
        "qwen3.5-9b-q4km": "Korgis · Qwen3.5 9B Q4_K_M",
        "qwen3.5-2b-q4km": "Korgis · Qwen3.5 2B Q4_K_M",
        "qwen3.5-0.8b-q4km": "Korgis · Qwen3.5 0.8B Q4_K_M",
        "nemotron-nano-4b": "Korgis · Nemotron Nano 4B Q4_K_M",
        "nemotron-nano-4b-q8": "Korgis · Nemotron Nano 4B Q8_0",
    },
}


@lru_cache(maxsize=1)
def load_reporting_config() -> dict[str, Any]:
    """Load configuration from YAML file or return defaults."""
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return _DEFAULT_CONFIG


def get_series_name(provider: str, model: str) -> str:
    """Format a consistent, legible display name for a model."""
    if provider == "jev":
        return f"Jev · {model}"
    if provider == "llm-monolithic":
        return f"{model} · monolithic"
    if provider == "local-korgis":
        labels = load_reporting_config().get("model_labels", {})
        return labels.get(model, f"Korgis · {model}")
    return model
