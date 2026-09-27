from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_capability_bench import build_task_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "tasks.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect the model capability benchmark task plugin catalog."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--tasks", default="all")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = build_task_registry(args.catalog)

    if args.tasks.strip().lower() == "all":
        selected = registry.select()
    else:
        task_ids = [
            task_id.strip()
            for task_id in args.tasks.split(",")
            if task_id.strip()
        ]
        selected = registry.select(task_ids)

    payload = {
        "summary": registry.summary(),
        "selected": [
            {
                "task_id": task.spec.task_id,
                "version": task.spec.version,
                "plugin_id": task.spec.plugin_id,
                "evaluator_id": task.spec.evaluator_id,
                "evaluator_version": task.spec.evaluator_version,
                "compatible_datasets": list(task.spec.compatible_datasets),
                "prompt_id": task.spec.prompt_id,
                "prompt_version": task.spec.prompt_version,
                "required_capabilities": {
                    "text_input": task.spec.required_capabilities.text_input,
                    "image_input": task.spec.required_capabilities.image_input,
                    "image_output": task.spec.required_capabilities.image_output,
                    "image_editing": task.spec.required_capabilities.image_editing,
                    "multi_image_input": (
                        task.spec.required_capabilities.multi_image_input
                    ),
                },
                "metrics": [
                    {
                        "name": metric.name,
                        "primary": metric.primary,
                    }
                    for metric in task.spec.metrics
                ],
            }
            for task in selected
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
