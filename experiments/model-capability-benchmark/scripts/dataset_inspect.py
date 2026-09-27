from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_core import DatasetLoadContext, load_dataset_profiles
from benchmark_core.config import parse_csv_selection

from model_capability_bench import build_dataset_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "datasets.yaml"
DEFAULT_PROFILES = ROOT / "profiles.yaml"
DEFAULT_CACHE = ROOT / "data" / "cache"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or load model capability benchmark datasets."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--datasets", default="all")
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--load", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = build_dataset_registry(args.catalog)
    profiles = load_dataset_profiles(args.profiles)
    try:
        profile = profiles[args.profile]
    except KeyError as exc:
        available = ", ".join(sorted(profiles))
        raise ValueError(
            f"Unknown profile {args.profile!r}; available: {available}"
        ) from exc

    dataset_ids = parse_csv_selection(
        args.datasets,
        available=list(registry.datasets),
    )
    selected = registry.select(dataset_ids)

    payload: dict[str, object] = {
        "summary": registry.summary(),
        "profile": {
            "profile_id": profile.profile_id,
            "default_max_cases": profile.default_max_cases,
        },
        "selected": [],
    }
    selected_payload: list[dict[str, object]] = []
    for dataset in selected:
        item: dict[str, object] = {
            "dataset_id": dataset.spec.dataset_id,
            "version": dataset.spec.version,
            "adapter_id": dataset.spec.adapter_id,
            "source": dataset.spec.source,
            "revision": dataset.spec.revision,
            "split": dataset.spec.split,
            "license": dataset.spec.license_id,
            "cache_mode": dataset.spec.cache_mode,
            "sample_schema_version": dataset.spec.sample_schema_version,
            "max_cases": profile.max_cases_for(dataset.spec.dataset_id),
        }
        if args.load:
            result = dataset.load(
                DatasetLoadContext(
                    cache_dir=args.cache_dir,
                    profile=profile,
                    seed=args.seed,
                )
            )
            item["load"] = {
                "selected_count": len(result.samples),
                "available_count": result.available_count,
                "selection_fingerprint": result.selection_fingerprint,
                "source_checksums": dict(result.source_checksums),
                "sample_ids": [sample.sample_id for sample in result.samples],
            }
        selected_payload.append(item)

    payload["selected"] = selected_payload
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
