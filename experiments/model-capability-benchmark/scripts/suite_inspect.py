from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_core.config import parse_csv_selection
from model_capability_bench import load_capability_suite

ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the composed model capability benchmark suite."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--models", default="all")
    parser.add_argument("--capabilities", default="all")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    bundle = load_capability_suite(args.root)

    model_keys = parse_csv_selection(
        args.models,
        available=list(bundle.models.models),
    )
    capability_ids = parse_csv_selection(
        args.capabilities,
        available=[
            capability.spec.capability_id
            for capability in bundle.resolved_capabilities
        ],
    )
    arms = bundle.plan_matrix(
        model_keys=model_keys,
        capability_ids=capability_ids,
    )

    payload = {
        "suite": {
            "suite_id": bundle.suite.suite_id,
            "version": bundle.suite.version,
            "default_profile": bundle.suite.default_profile,
            "generation": {
                "temperature": bundle.suite.generation.temperature,
                "max_output_tokens": bundle.suite.generation.max_output_tokens,
                "seed": bundle.suite.generation.seed,
            },
        },
        "capabilities": [
            {
                "capability_id": capability.spec.capability_id,
                "task_id": capability.spec.task_id,
                "dataset_ids": list(capability.spec.dataset_ids),
                "primary_metric": next(
                    metric.name
                    for metric in capability.spec.metrics
                    if metric.primary
                ),
                "metrics": [
                    {
                        "name": metric.name,
                        "source": metric.source,
                        "reducer": metric.reducer,
                        "field": metric.field,
                        "primary": metric.primary,
                    }
                    for metric in capability.spec.metrics
                ],
                "context": [
                    {
                        "key": binding.key,
                        "source": binding.source,
                        "dataset_id": binding.dataset_id,
                        "field": binding.field,
                    }
                    for binding in capability.spec.context_bindings
                ],
            }
            for capability in bundle.resolved_capabilities
            if capability.spec.capability_id in set(capability_ids)
        ],
        "models": model_keys,
        "matrix": [
            {
                "model_key": arm.model_key,
                "capability_id": arm.capability_id,
                "task_id": arm.task_id,
                "dataset_id": arm.dataset_id,
                "runtime_key": arm.runtime_key,
                "provider_key": arm.provider_key,
            }
            for arm in arms
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
