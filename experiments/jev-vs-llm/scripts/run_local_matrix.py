#!/usr/bin/env python3
"""run_local_matrix.py.

CLI tool for autonomous local benchmark execution across one or more models.
Usage examples:
  # Run routing smoke test on specific models:
  uv run python scripts/run_local_matrix.py --models qwen3.5-0.8b-q4km,nemotron-nano-4b

  # Run all configured models with public budget profile:
  uv run python scripts/run_local_matrix.py --models all --dataset public --profile budget

  # Interactive model selection menu:
  uv run python scripts/run_local_matrix.py -i

  # List available configured models:
  uv run python scripts/run_local_matrix.py --list
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path so jev_bench can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from benchmark_core import RegistryError, load_registry
from benchmark_core.config import (
    ConfigError,
    load_yaml_mapping,
    load_yaml_section,
    parse_csv_selection,
)

from scripts.korgis_manager import KorgisManager
from scripts.runner_orchestrator import ExperimentOrchestrator

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "experiments_config.yaml"


def load_config(config_path: Path) -> dict[str, Any]:
    """Compatibility wrapper over the shared benchmark YAML loader."""
    return load_yaml_mapping(config_path)


def load_registry_models(registry_path: Path) -> dict[str, dict[str, Any]]:
    """Expose typed models while preserving the historical models-only wrapper."""
    try:
        bundle = load_registry(registry_path)
    except RegistryError:
        return load_yaml_section(registry_path, "models")

    result: dict[str, dict[str, Any]] = {}
    for key, spec in bundle.models.items():
        result[key] = {
            "model_id": spec.model_id,
            "runtime_model_id": spec.runtime_model_id,
            "quantization": (
                spec.artifact.quantization
                if spec.artifact is not None
                else None
            ),
            "tags": list(spec.tags),
        }
    return result


def prompt_interactive_selection(available: dict[str, dict[str, Any]]) -> list[str]:
    """Present a simple CLI menu for selecting models."""
    keys = list(available.keys())
    print("\n--- Available Local Models ---")
    for idx, key in enumerate(keys, start=1):
        info = available[key]
        desc = f"{info.get('model_id', key)} ({info.get('quantization', 'GGUF')})"
        print(f"  [{idx}] {key.ljust(20)} -> {desc}")
    print("  [a] All of the above")

    choice = input("\nEnter model numbers to evaluate (e.g. 1,2 or a) [default: a]: ").strip().lower()
    if not choice or choice == "a":
        return keys

    selected: list[str] = []
    for part in choice.replace(" ", "").split(","):
        if part.isdigit():
            i = int(part) - 1
            if 0 <= i < len(keys):
                selected.append(keys[i])
            else:
                print(f"Warning: Index {part} out of range, skipped.")
    return selected or keys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local LLM decision benchmarks autonomously one model at a time.",
    )
    parser.add_argument(
        "-m", "--models",
        help="Comma-separated model keys or 'all'. Defaults to config default_models.",
    )
    parser.add_argument(
        "-e", "--experiments",
        help="Comma-separated experiment names (routing, calibration, scaling, workflow, agent).",
    )
    parser.add_argument(
        "-d", "--dataset",
        choices=["smoke", "public"],
        help="Benchmark tier: 'smoke' or 'public'.",
    )
    parser.add_argument(
        "-p", "--profile",
        choices=["budget", "quick", "standard", "full"],
        help="Profile for public dataset runs.",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to runner configuration YAML file.",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactively select models from menu.",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available configured local models and exit.",
    )
    parser.add_argument(
        "--keep-korgis",
        action="store_true",
        help="Keep Korgis server running after benchmark completes.",
    )

    args = parser.parse_args()

    # Load configuration
    cfg = load_config(args.config)
    log_level = cfg.get("log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        l = logging.getLogger(noisy)
        l.setLevel(logging.WARNING)
        l.propagate = False

    registry_rel = cfg.get("benchmark_registry_path", "models.yaml")
    registry_file = (PROJECT_ROOT / registry_rel).resolve()
    available_models = load_registry_models(registry_file)

    if args.list:
        print("\nConfigured Local Benchmark Models:")
        for k, v in available_models.items():
            quantization = v.get("quantization") or "unquantized"
            print(
                f"  • {k.ljust(22)}: {v.get('model_id')} "
                f"({quantization})"
            )
        return 0

    # Resolve models to run
    chosen_models: list[str] = []
    if args.interactive or (not args.models and sys.stdin.isatty() and not cfg.get("default_models")):
        chosen_models = prompt_interactive_selection(available_models)
    elif args.models:
        try:
            chosen_models = parse_csv_selection(
                args.models,
                available=list(available_models.keys()),
            )
        except ConfigError:
            chosen_models = []
    else:
        chosen_models = list(cfg.get("default_models") or available_models.keys())

    if not chosen_models:
        print("Error: No models selected.", file=sys.stderr)
        return 1

    dataset = args.dataset or cfg.get("dataset", "smoke")
    profile = args.profile or cfg.get("public_profile", "budget")

    # Ensure llama-server doesn't divert output tokens to reasoning traces (<think>) for structured JSON evaluation
    os.environ.setdefault("LLAMA_ARG_REASONING", "off")

    # Use explicit environment or PATH discovery; never guess machine-specific paths.
    if "LOCAL_LLM_SERVER_BIN" not in os.environ:
        discovered_bin = shutil.which("llama-server")
        if discovered_bin:
            os.environ["LOCAL_LLM_SERVER_BIN"] = discovered_bin

    # Resolve experiments
    if args.experiments:
        raw_exp = args.experiments.strip().lower()
        if raw_exp == "all":
            if dataset == "public":
                experiments = ["routing", "calibration"]
            else:
                experiments = ["routing", "calibration", "scaling", "workflow", "agent"]
        else:
            experiments = [e.strip() for e in args.experiments.split(",") if e.strip()]
    else:
        experiments = list(cfg.get("default_experiments", ["routing"]))
    base_url = cfg.get("korgis_base_url", "http://127.0.0.1:1235/v1")
    korgis_dir = os.getenv("KORGIS_DIR") or cfg.get("korgis_dir")
    max_tokens = int(cfg.get("max_output_tokens", 512))

    print("\n" + "=" * 65)
    print("      AUTONOMOUS LOCAL MODEL BENCHMARK ORCHESTRATOR")
    print("=" * 65)
    print(f"Models to evaluate  : {', '.join(chosen_models)}")
    print(f"Experiments to run  : {', '.join(experiments)}")
    print(f"Dataset tier        : {dataset} (profile: {profile})")
    print(f"Korgis Base URL     : {base_url}")
    print(f"Max Output Tokens   : {max_tokens}")
    print("=" * 65 + "\n")

    # Initialize Korgis Manager
    korgis = KorgisManager(
        base_url=base_url,
        korgis_dir=korgis_dir,
        registry_path=None,
        timeout=float(cfg.get("korgis_control_timeout", 360)),
    )

    try:
        korgis.ensure_running(initial_model=chosen_models[0])

        orchestrator = ExperimentOrchestrator(
            korgis_manager=korgis,
            output_csv=PROJECT_ROOT / cfg.get("results_csv", "results/raw/local_results.csv"),
            report_html=PROJECT_ROOT / cfg.get("report_html", "results/local_report.html"),
            max_output_tokens=max_tokens,
        )

        results = orchestrator.run_matrix(
            models=chosen_models,
            experiments=experiments,
            dataset=dataset,
            profile=profile,
        )

        # Print Final Summary Table
        print("\n" + "=" * 65)
        print("                  FINAL BENCHMARK SUMMARY")
        print("=" * 65)
        print(f"{'Model':<22} {'Exp':<12} {'Valid':<10} {'Accuracy':<10} {'Latency':<10}")
        print("-" * 65)
        for rec in results.get("summary", []):
            if rec.get("status") == "SUCCESS":
                valid_str = f"{rec['valid_cases']}/{rec['total_cases']}"
                acc_str = f"{rec['accuracy_pct']}%"
                lat_str = f"{rec['avg_latency_ms']}ms"
                print(f"{rec['model']:<22} {rec['experiment']:<12} {valid_str:<10} {acc_str:<10} {lat_str:<10}")
            else:
                print(f"{rec['model']:<22} {rec.get('experiment', 'N/A'):<12} {'FAILED':<10} {rec.get('error', '')}")
        print("=" * 65)
        print(f"HTML Dashboard : file://{results['report_html']}")
        print(f"Raw Results CSV: {results['output_csv']}")
        print("=" * 65 + "\n")

    finally:
        should_stop = cfg.get("stop_korgis_on_complete", True) and not args.keep_korgis
        if should_stop:
            korgis.stop_server()

    return 0


if __name__ == "__main__":
    sys.exit(main())
