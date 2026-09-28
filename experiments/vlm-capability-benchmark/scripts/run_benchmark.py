from __future__ import annotations

import argparse
import os
from pathlib import Path

from vlm_bench.planning import build_run_plan
from vlm_bench.runner import execute_run_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VLM capability benchmark")
    parser.add_argument(
        "--models",
        required=True,
        help="Comma-separated model keys from models.yaml",
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve config and selected cases without invoking the model",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    model_keys = [item.strip() for item in args.models.split(",") if item.strip()]
    plan = build_run_plan(
        root,
        model_keys=model_keys,
        profile_id=args.profile,
    )

    if args.dry_run:
        print(f"suite={plan.suite_id} profile={plan.profile_id} seed={plan.seed}")
        print("models=" + ",".join(model.model_key for model in plan.models))
        print("samples=" + ",".join(case.sample_id for case in plan.cases))
        print(f"prompt_sha256={plan.prompt_sha256}")
        return 0

    rows = execute_run_plan(
        plan,
        output_dir=args.output_dir,
        environ=os.environ,
    )
    succeeded = sum(bool(row["valid"]) for row in rows)
    print(f"completed={len(rows)} valid={succeeded} output={args.output_dir}")
    return 0 if succeeded == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
