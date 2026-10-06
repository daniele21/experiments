from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_manifest, load_models, select_models
from .runner import plan, run
from .runtime import FluidAudioRuntime


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _models_path(root: Path) -> Path:
    return root / "models.yaml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="diarization-bench")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--build", action="store_true")

    sub.add_parser("build-helper")

    plan_cmd = sub.add_parser("plan")
    plan_cmd.add_argument("--manifest", type=Path, required=True)
    plan_cmd.add_argument("--models", default="all")

    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--manifest", type=Path, required=True)
    run_cmd.add_argument("--models", default="all")
    run_cmd.add_argument("--run-id")
    run_cmd.add_argument("--build-helper", action="store_true")

    return parser


def main() -> int:
    args = _parser().parse_args()
    root = _root()
    runtime = FluidAudioRuntime(root)

    if args.command == "preflight":
        problems = runtime.preflight()
        if args.build and not problems:
            runtime.build()
        payload = {
            "ok": not problems,
            "problems": problems,
            "helper": str(runtime.binary_path),
            "helper_exists": runtime.binary_path.exists(),
        }
        print(json.dumps(payload, indent=2))
        return 0 if not problems else 2

    if args.command == "build-helper":
        runtime.build()
        print(runtime.binary_path)
        return 0

    models = select_models(load_models(_models_path(root)), args.models)
    cases = load_manifest(args.manifest)

    if args.command == "plan":
        print(json.dumps(plan(models, cases), indent=2))
        return 0

    if args.build_helper:
        runtime.build()
    run_dir = run(root, models, cases, run_id=args.run_id)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
