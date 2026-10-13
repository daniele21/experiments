"""Opt-in synthetic-only cloud baseline in the ordinary RedactBench suite layout."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redact_bench.cloud_provider import SUPPORTED_CLOUD_MODELS
from redact_bench.datasets import load_dataset
from redact_bench.progress import TerminalProgress
from redact_bench.runner import run_compare

# Only explicitly versioned synthetic fixtures are permitted to leave this Mac.
# No path from a CLI argument is ever uploaded merely because it exists.
SYNTHETIC_FIXTURES = {
    "healthcare": "data/healthcare/cases.jsonl",
    "ambiguous": "data/ambiguous/cases.jsonl",
    "challenge": "data/challenge/cases.jsonl",
}
# Standard USD / million tokens; indicative, billed amounts may differ.
LUNA_INPUT_USD_PER_M = 0.10
LUNA_OUTPUT_USD_PER_M = 0.50


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cloud_dataset(root: Path, name: str) -> Path:
    rel = SYNTHETIC_FIXTURES.get(name)
    if not rel:
        raise ValueError(
            "Cloud evaluation only accepts bundled synthetic datasets: "
            + ", ".join(SYNTHETIC_FIXTURES)
        )
    path = (root / rel).resolve(strict=True)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Dataset is outside the checked experiment directory.")
    return path


def prepare_cloud_reference(
    *, experiment_root: Path, dataset: str, model: str, max_cases: int | None,
) -> dict:
    if model not in SUPPORTED_CLOUD_MODELS:
        raise ValueError("Unsupported cloud model. Supported: " + ", ".join(SUPPORTED_CLOUD_MODELS))
    source = cloud_dataset(experiment_root, dataset)
    cases = load_dataset(source)
    if max_cases is not None and not 1 <= max_cases <= len(cases):
        raise ValueError(f"max_cases must be between 1 and {len(cases)}")
    selected = cases[:max_cases] if max_cases else cases
    versions = {case.gold_version for case in cases}
    if len(versions) != 1 or not next(iter(versions)):
        raise ValueError("The cloud baseline requires a single frozen gold version.")
    if dataset != "challenge" and any("synthetic" not in case.tags for case in cases):
        raise ValueError("Only cases explicitly tagged synthetic are allowed in cloud benchmarks.")
    return {
        "source": source,
        "model": model,
        "cases": selected,
        "total_cases": len(cases),
        "dataset_id": next(iter(versions)),
        "dataset_key": dataset,
        "scope": "smoke" if max_cases else "full",
    }


def estimate_tokens(result_dir: Path, model: str) -> dict:
    input_tokens = output_tokens = 0
    path = result_dir / f"{model.replace('/', '_')}.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            obj = row.get("result") or row.get("preflight") or {}
            input_tokens += obj.get("input_tokens") or 0
            output_tokens += obj.get("output_tokens") or 0
    return {
        "input_tokens_observed": input_tokens,
        "output_tokens_observed": output_tokens,
        "usd_estimate_unadjusted": round(
            (input_tokens * LUNA_INPUT_USD_PER_M +
             output_tokens * LUNA_OUTPUT_USD_PER_M) / 1_000_000, 6
        ),
        "cost_note": "Estimate only, using standard uncached public token rates; actual billing may differ.",
    }


def run_cloud_reference(
    *, experiment_root: Path, dataset: str = "healthcare",
    model: str = "gpt-6-luna", max_cases: int | None = None,
    confirm_cloud: bool = False,
) -> Path:
    plan = prepare_cloud_reference(
        experiment_root=experiment_root, dataset=dataset, model=model, max_cases=max_cases,
    )
    if not confirm_cloud:
        raise ValueError(
            "Explicit --confirm-cloud required: sends synthetic benchmark text "
            "and RedactGuard prompts to the OpenAI API, with token charges."
        )
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY missing. ChatGPT subscription is separate from OpenAI API billing."
        )
    suite_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + (
        "-suite-cloud-" + uuid.uuid4().hex[:8]
    )
    suite_dir = experiment_root / "results" / "suites" / suite_id
    suite_dir.mkdir(parents=True, exist_ok=False)
    status_file = suite_dir / "suite.json"
    baseline = {
        "suite_id": suite_id,
        "dataset_id": plan["dataset_id"],
        "dataset_key": plan["dataset_key"],
        "models": [model],
        "backend": "openai_api",
        "provider": "openai",
        "cloud_explicit_consent": True,
        "quality_only": True,
        "benchmark_scope": plan["scope"],
        "selected_cases": len(plan["cases"]),
        "total_cases": plan["total_cases"],
        "started_at": _iso(),
    }
    status_file.write_text(json.dumps({**baseline, "status": "running"}, indent=2))
    try:
        print(
            f"[RedactBench cloud] Sending {len(plan['cases'])} synthetic cases "
            f"({dataset}) to OpenAI API model {model}. No Korgis/GGUF involved.",
            flush=True,
        )
        result = run_compare(
            models=[model],
            dataset_path=str(plan["source"]),
            profiles_path=str(experiment_root / "config/profiles.yaml"),
            results_dir=str(suite_dir / "_work"),
            warmups=0,
            progress=TerminalProgress(),
            preflight=True,
            case_ids=[case.case_id for case in plan["cases"]],
            backend="openai_api",
        )
        target = suite_dir / "quality"
        shutil.move(str(result), str(target))
        shutil.rmtree(suite_dir / "_work", ignore_errors=True)
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "suite_id": suite_id,
            "dataset_id": plan["dataset_id"],
            "backend": "openai_api",
            "cloud_data_policy": "bundled_synthetic_only",
            "benchmark_scope": plan["scope"],
        })
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        usage = estimate_tokens(target, model)
        status_file.write_text(json.dumps({
            **baseline, "status": "completed", "completed_at": _iso(),
            "quality": str(target), "latency": None, "usage_estimate": usage,
        }, indent=2))
        print(f"[RedactBench cloud] Quality results: {target}", flush=True)
        print(f"[RedactBench cloud] Token-based indicative cost: "
              f"${usage['usd_estimate_unadjusted']:.4f} USD (excluding discounts).", flush=True)
        return suite_dir
    except BaseException as exc:
        status_file.write_text(json.dumps({
            **baseline, "status": "failed", "failed_at": _iso(),
            "error_type": type(exc).__name__,
        }, indent=2))
        raise
