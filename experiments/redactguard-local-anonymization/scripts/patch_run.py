#!/usr/bin/env python3
"""
scripts/patch_run.py

Consolidates targeted remediation runs into a comprehensive baseline run.
Patches rows.json, <model>.jsonl, metrics.json, failures.json, and report.html.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Add src to python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from redact_bench.metrics import aggregate_detailed
from redact_bench.report import write_html


def patch_run(
    target_dir: Path,
    source_dirs: list[Path],
    backup: bool = True,
) -> None:
    if not target_dir.is_dir():
        print(f"Error: Target directory {target_dir} not found.")
        sys.exit(1)

    print(f"=== Consolidating remediation runs into {target_dir.name} ===")

    # Create backup if requested
    if backup:
        backup_dir = target_dir.parent / f"{target_dir.name}.backup"
        if not backup_dir.exists():
            print(f"Creating backup at {backup_dir.name}...")
            shutil.copytree(target_dir, backup_dir)
        else:
            print(f"Backup already exists at {backup_dir.name}.")

    # Load target rows
    rows_path = target_dir / "rows.json"
    manifest_path = target_dir / "manifest.json"
    metrics_path = target_dir / "metrics.json"
    failures_path = target_dir / "failures.json"
    report_path = target_dir / "report.html"

    if not rows_path.exists():
        print(f"Error: {rows_path} does not exist.")
        sys.exit(1)

    target_rows = json.loads(rows_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    # Collect available replacement rows from source remediation runs
    replacements: dict[tuple[str, str], dict] = {}
    jsonl_replacements: dict[tuple[str, str], dict] = {}

    for src in source_dirs:
        if not src.is_dir():
            continue
        src_rows_path = src / "rows.json"
        if not src_rows_path.exists():
            continue
        src_rows = json.loads(src_rows_path.read_text(encoding="utf-8"))
        for row in src_rows:
            model = row.get("model")
            case_id = row.get("case_id")
            valid = row.get("valid", False)
            if model and case_id and valid:
                replacements[(model, case_id)] = row

        # Also collect jsonl row objects for model jsonl files
        for jsonl_file in src.glob("*.jsonl"):
            model = jsonl_file.stem
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    cid = obj.get("case_id") or obj.get("case", {}).get("id")
                    if cid and obj.get("score", {}).get("valid", False):
                        jsonl_replacements[(model, cid)] = obj

    print(f"Found {len(replacements)} successful remediation case(s) to patch:")
    for (model, cid) in replacements:
        print(f"  + {model} :: {cid}")

    # Patch rows
    patched_count = 0
    new_rows = []
    for row in target_rows:
        key = (row.get("model"), row.get("case_id"))
        if key in replacements:
            print(f"Patching row for {key[0]} - {key[1]} (valid: {row.get('valid')} -> True)")
            new_rows.append(replacements[key])
            patched_count += 1
        else:
            new_rows.append(row)

    if patched_count == 0:
        print("No matching failing rows were found to patch.")
        return

    # Update rows.json
    rows_path.write_text(json.dumps(new_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # Patch model-specific jsonl files
    models = sorted({r.get("model") for r in new_rows if r.get("model")})
    all_summaries: dict[str, dict] = {}

    for model in models:
        model_rows = [r for r in new_rows if r.get("model") == model]
        summary = aggregate_detailed(model_rows)
        all_summaries[model] = summary

        # Update <model>.jsonl
        jsonl_path = target_dir / f"{model}.jsonl"
        if jsonl_path.exists():
            existing_objs = []
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    cid = obj.get("case_id") or obj.get("case", {}).get("id")
                    key = (model, cid)
                    if key in jsonl_replacements:
                        existing_objs.append(jsonl_replacements[key])
                    else:
                        existing_objs.append(obj)
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for obj in existing_objs:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # Write updated metrics.json
    metrics_path.write_text(json.dumps(all_summaries, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write updated failures.json
    failures_data = {
        model: summary.get("failure_analysis", [])
        for model, summary in all_summaries.items()
    }
    failures_path.write_text(json.dumps(failures_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write updated report.html
    if manifest:
        try:
            write_html(report_path, all_summaries, manifest)
        except Exception as e:
            print(f"Warning: Could not regenerate report.html: {e}")

    print("\n✓ Patch complete! Updated metrics:")
    for model, summary in all_summaries.items():
        micro = summary.get("micro", {})
        print(
            f"  • {model}: cases={micro.get('cases')}, "
            f"failures={micro.get('failures')}, "
            f"status={micro.get('status')}, "
            f"recall={micro.get('pii_recall', 0)*100:.1f}%, "
            f"precision={micro.get('precision', 0)*100:.1f}%"
        )


def main():
    parser = argparse.ArgumentParser(description="Consolidate remediation runs into baseline run.")
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("results/20260929T070819Z-e9070dbe"),
        help="Target baseline run directory to patch",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        nargs="*",
        default=[
            Path("results/20260929T103538Z-0333e2e3"),
            Path("results/20260929T104333Z-f1bf0f7d"),
        ],
        help="Source remediation run directories",
    )
    args = parser.parse_args()
    patch_run(args.target, args.sources)


if __name__ == "__main__":
    main()
