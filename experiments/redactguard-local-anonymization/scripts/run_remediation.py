#!/usr/bin/env python3
"""Run targeted remediation benchmark on specific failing models and documents.

Allows selective re-execution of failed cases without re-evaluating cases
that already completed successfully.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from redact_bench.datasets import load_dataset
from redact_bench.metrics import aggregate_detailed, score_case
from redact_bench.models import Case
from redact_bench.progress import TerminalProgress
from redact_bench.provider import KorgisController, KorgisRedactProvider
from redact_bench.report import write_html
from redact_bench.runner import run_compare


def load_config(config_path: Path) -> dict[str, Any]:
    """Load remediation targets from YAML configuration."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _patch_run_directory(
    run_dir: Path,
    new_results_by_model: dict[str, list[dict]],
) -> None:
    """Patch an existing benchmark run directory with newly evaluated cases.

    Creates a .bak backup before modifying any files, updates the JSONL files,
    and recalculates metrics.json, failures.json, rows.json, manifest.json,
    and report.html.
    """
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    backup_dir = run_dir.parent / f"{run_dir.name}.bak"
    if not backup_dir.exists():
        print(f"Creating backup at: {backup_dir}")
        shutil.copytree(run_dir, backup_dir)

    all_updated_rows = []
    summaries = {}

    for model, new_entries in new_results_by_model.items():
        model_file = run_dir / f"{model.replace('/', '_')}.jsonl"
        existing_entries = []
        if model_file.exists():
            with model_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        existing_entries.append(json.loads(line))

        # Index new entries by case_id
        new_by_case = {
            entry["score"]["case_id"]: entry for entry in new_entries if "score" in entry
        }

        # Merge: update existing entries or append new ones
        merged_entries = []
        replaced_cases = set()
        for entry in existing_entries:
            case_id = entry.get("score", {}).get("case_id") or entry.get("case", {}).get("id")
            if case_id in new_by_case:
                merged_entries.append(new_by_case[case_id])
                replaced_cases.add(case_id)
            else:
                merged_entries.append(entry)

        for case_id, entry in new_by_case.items():
            if case_id not in replaced_cases:
                merged_entries.append(entry)

        # Write updated JSONL
        with model_file.open("w", encoding="utf-8") as f:
            for entry in merged_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Extract scored rows for metrics recalculation
        model_rows = [entry["score"] for entry in merged_entries if "score" in entry]
        all_updated_rows.extend(model_rows)
        summaries[model] = aggregate_detailed(model_rows)

    # Update summary files
    manifest_path = run_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    manifest["remediated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["remediated_models"] = list(new_results_by_model.keys())

    (run_dir / "metrics.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "failures.json").write_text(
        json.dumps(
            {
                model: summary.get("failure_analysis", [])
                for model, summary in summaries.items()
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "rows.json").write_text(
        json.dumps(all_updated_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_html(run_dir / "report.html", summaries, manifest)
    print(f"\n[OK] Run {run_dir.name} successfully patched with remediated results!")


def evaluate_model_cases(
    model: str,
    cases: list[Case],
    profiles_path: Path,
    timeout: float | None = None,
    chunk_max_chars: int | None = None,
    adaptive_subdivision: bool = True,
) -> list[dict]:
    """Evaluate a single model against a specific list of Cases."""
    controller = KorgisController()
    controller.health()
    controller.activate(model)

    provider = KorgisRedactProvider(
        model,
        str(profiles_path),
        timeout=timeout,
        chunk_max_chars=chunk_max_chars,
        adaptive_subdivision=adaptive_subdivision,
    )

    results = []
    print(f"\n---> Evaluating {model} on {len(cases)} case(s)...")
    for idx, case in enumerate(cases, start=1):
        print(f"  [{idx}/{len(cases)}] Case: {case.case_id}...", end="", flush=True)
        res = provider.evaluate(case)
        status = "OK" if res.valid else f"FAILED ({res.error_type})"
        print(f" {status} (latency: {res.latency_ms:.1f}ms, findings: {len(res.findings)})")
        score = score_case(case, res)
        results.append(
            {
                "case": {
                    "id": case.case_id,
                    "profile": case.profile,
                    "tags": case.tags,
                    "gold": [asdict(span) for span in case.gold],
                },
                "result": res.to_dict(),
                "score": score,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Targeted remediation benchmark for RedactBench."
    )
    parser.add_argument(
        "--target",
        choices=["qwen", "nemotron", "nemotron-q8", "all"],
        default="all",
        help="Remediation target profile to execute (default: all).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config/remediation_targets.yaml",
        help="Path to remediation targets YAML config.",
    )
    parser.add_argument(
        "--patch-run",
        type=str,
        default=None,
        help="Run ID to patch (e.g. 20260929T070819Z-e9070dbe). If set, updates the run in-place.",
    )
    parser.add_argument(
        "--patch-latest",
        action="store_true",
        help="Automatically patch the latest run (20260929T070819Z-e9070dbe).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=360.0,
        help="Per-segment timeout in seconds (default: 360).",
    )
    parser.add_argument(
        "--chunk-max-chars",
        type=int,
        default=4000,
        help="Max characters per chunk segment (default: 4000).",
    )
    parser.add_argument(
        "--no-adaptive-subdivision",
        action="store_true",
        help="Disable adaptive subdivision for dense segments.",
    )

    args = parser.parse_args()
    config = load_config(args.config)
    dataset_path = PROJECT_ROOT / config.get("dataset", "data/realistic")
    profiles_path = PROJECT_ROOT / config.get("profiles", "config/profiles.yaml")
    results_dir = PROJECT_ROOT / config.get("results_dir", "results")

    # Load all dataset cases
    all_cases = load_dataset(dataset_path)
    cases_by_id = {c.case_id: c for c in all_cases}

    target_cfg = config["targets"][args.target]
    print(f"Target: {target_cfg['name']} - {target_cfg['description']}")

    # Determine patch run if requested
    patch_target = args.patch_run
    if args.patch_latest and not patch_target:
        # Default latest run with known errors
        patch_target = "20260929T070819Z-e9070dbe"

    # Prepare model -> cases mapping
    model_cases_map: dict[str, list[str]] = {}
    if "model_cases" in target_cfg:
        model_cases_map = target_cfg["model_cases"]
    else:
        for model in target_cfg["models"]:
            model_cases_map[model] = target_cfg["cases"]

    # If not patching an existing run, run standalone compare runs
    if not patch_target:
        for model, case_names in model_cases_map.items():
            print(f"\nRunning standalone benchmark for {model} on {case_names}...")
            output_path = run_compare(
                models=[model],
                dataset_path=str(dataset_path),
                profiles_path=str(profiles_path),
                results_dir=str(results_dir),
                warmups=0,
                progress=TerminalProgress(),
                preflight=True,
                timeout=args.timeout,
                chunk_max_chars=args.chunk_max_chars,
                adaptive_subdivision=not args.no_adaptive_subdivision,
                case_ids=case_names,
            )
            print(f"Created run output: {output_path}")
        return

    # Patch mode: evaluate missing cases and patch existing run
    run_dir = results_dir / patch_target
    if not run_dir.exists():
        print(f"Error: target run directory {run_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    evaluated_by_model: dict[str, list[dict]] = {}
    for model, case_names in model_cases_map.items():
        target_cases = [cases_by_id[name] for name in case_names if name in cases_by_id]
        new_entries = evaluate_model_cases(
            model=model,
            cases=target_cases,
            profiles_path=profiles_path,
            timeout=args.timeout,
            chunk_max_chars=args.chunk_max_chars,
            adaptive_subdivision=not args.no_adaptive_subdivision,
        )
        evaluated_by_model[model] = new_entries

    _patch_run_directory(run_dir, evaluated_by_model)


if __name__ == "__main__":
    main()
