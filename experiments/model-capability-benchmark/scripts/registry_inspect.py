from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from benchmark_core import load_registry, preflight_models, registry_summary
from benchmark_core.config import parse_csv_selection

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "models.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and preflight the model capability benchmark registry."
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--models", default="all")
    parser.add_argument("--deployment")
    parser.add_argument("--family")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--max-parameters-b", type=float)
    parser.add_argument("--quantization")
    parser.add_argument("--preflight", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = load_registry(args.registry)
    available = list(registry.models)
    model_keys = parse_csv_selection(args.models, available=available)

    selected = registry.select(
        model_keys=model_keys,
        tags=args.tag,
        deployment=args.deployment,
        family=args.family,
        max_parameters_b=args.max_parameters_b,
        quantization=args.quantization,
    )

    payload = {
        "registry": registry_summary(registry),
        "selected": [
            {
                "model_key": item.model.model_key,
                "model_id": item.model.model_id,
                "runtime_model_id": item.effective_model_id,
                "runtime_key": item.runtime.runtime_key,
                "deployment": item.runtime.deployment,
                "provider_key": item.provider.provider_key,
                "family": item.model.family,
                "parameters_b": item.model.parameters_b,
                "quantization": (
                    item.model.artifact.quantization
                    if item.model.artifact is not None
                    else None
                ),
                "tags": list(item.model.tags),
            }
            for item in selected
        ],
    }

    if args.preflight:
        result = preflight_models(registry, selected, os.environ)
        payload["preflight"] = {
            "ok": result.ok,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "provider_key": issue.provider_key,
                    "env_var": issue.env_var,
                }
                for issue in result.issues
            ],
        }
        if not result.ok:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
