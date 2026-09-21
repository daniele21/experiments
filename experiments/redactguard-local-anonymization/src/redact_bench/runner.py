from __future__ import annotations

import json
import os
import platform
import subprocess
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from redact_bench.datasets import load_jsonl
from redact_bench.metrics import aggregate, score_case
from redact_bench.provider import KorgisController, KorgisRedactProvider
from redact_bench.report import write_html

KORGIS_REPOSITORY = "daniele21/korgis"
KORGIS_TESTED_REF = "dev"
KORGIS_TESTED_SHA = "26a161dc0ef89a133c7a076d3a31544a274c1469"
REDACTGUARD_REPOSITORY = "daniele21/redact-guard"
REDACTGUARD_CONTRACT_SHA = "70ea5ed4fbbd7182010cc04eb756f636791c5947"


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def run_compare(
    *,
    models: list[str],
    dataset_path: str,
    profiles_path: str,
    results_dir: str,
    warmups: int = 1,
) -> Path:
    controller = KorgisController()
    controller.health()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(results_dir) / run_id
    output.mkdir(parents=True, exist_ok=True)

    cases = load_jsonl(dataset_path)
    summaries: dict[str, dict] = {}
    identities: dict[str, dict | None] = {}
    all_rows: list[dict] = []

    for model in models:
        controller.activate(model)
        identities[model] = controller.model_identity(model)
        provider = KorgisRedactProvider(model, profiles_path)

        for case in cases[: min(warmups, len(cases))]:
            provider.evaluate(case)

        model_rows = []
        raw_path = output / f"{model.replace('/', '_')}.jsonl"
        with raw_path.open("w", encoding="utf-8") as raw_file:
            for case in cases:
                result = provider.evaluate(case)
                row = score_case(case, result)
                model_rows.append(row)
                all_rows.append(row)
                raw_file.write(
                    json.dumps(
                        {
                            "case": {
                                "id": case.case_id,
                                "profile": case.profile,
                                "tags": case.tags,
                                "gold": [asdict(span) for span in case.gold],
                            },
                            "result": result.to_dict(),
                            "score": row,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        summaries[model] = aggregate(model_rows)

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_commit": _git_sha(),
        "dataset": str(Path(dataset_path)),
        "cases": len(cases),
        "models": models,
        "korgis": {
            "repository": KORGIS_REPOSITORY,
            "tested_ref": KORGIS_TESTED_REF,
            "tested_sha": KORGIS_TESTED_SHA,
            "base_url": os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1"),
            "runtime_identity": identities,
        },
        "redactguard_contract": {
            "repository": REDACTGUARD_REPOSITORY,
            "source_sha": REDACTGUARD_CONTRACT_SHA,
            "scope": "prompt taxonomy + model-value-to-source-span post-processing",
        },
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "warmups_per_model": warmups,
    }
    (output / "metrics.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "rows.json").write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_html(output / "report.html", summaries, manifest)
    return output


def run_latency(
    *,
    models: list[str],
    dataset_path: str,
    profiles_path: str,
    results_dir: str,
    warmups: int = 5,
    repeats: int = 30,
    case_ids: list[str] | None = None,
) -> Path:
    controller = KorgisController()
    controller.health()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-latency-" + uuid.uuid4().hex[:8]
    output = Path(results_dir) / run_id
    output.mkdir(parents=True, exist_ok=True)

    all_cases = load_jsonl(dataset_path)
    selected_ids = case_ids or ["g01", "g04", "h05", "f01", "l02"]
    by_id = {case.case_id: case for case in all_cases}
    cases = [by_id[case_id] for case_id in selected_ids if case_id in by_id]
    if not cases:
        raise ValueError("No latency cases selected")

    summaries: dict[str, dict] = {}
    identities: dict[str, dict | None] = {}
    all_rows: list[dict] = []

    for model in models:
        controller.activate(model)
        identities[model] = controller.model_identity(model)
        provider = KorgisRedactProvider(model, profiles_path)

        for _ in range(warmups):
            provider.evaluate(cases[0])

        model_rows: list[dict] = []
        raw_path = output / f"{model.replace('/', '_')}.jsonl"
        with raw_path.open("w", encoding="utf-8") as raw_file:
            for case in cases:
                for repeat in range(repeats):
                    result = provider.evaluate(case)
                    row = score_case(case, result)
                    row["repeat"] = repeat
                    model_rows.append(row)
                    all_rows.append(row)
                    raw_file.write(
                        json.dumps(
                            {
                                "case_id": case.case_id,
                                "repeat": repeat,
                                "result": result.to_dict(),
                                "score": row,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
        summaries[model] = aggregate(model_rows)

    manifest = {
        "run_id": run_id,
        "kind": "latency",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_commit": _git_sha(),
        "dataset": str(Path(dataset_path)),
        "case_ids": [case.case_id for case in cases],
        "repeats_per_case": repeats,
        "warmups_per_model": warmups,
        "models": models,
        "korgis": {
            "repository": KORGIS_REPOSITORY,
            "tested_ref": KORGIS_TESTED_REF,
            "tested_sha": KORGIS_TESTED_SHA,
            "base_url": os.getenv("KORGIS_BASE_URL", "http://127.0.0.1:1235/v1"),
            "runtime_identity": identities,
        },
        "redactguard_contract": {
            "repository": REDACTGUARD_REPOSITORY,
            "source_sha": REDACTGUARD_CONTRACT_SHA,
        },
    }
    (output / "metrics.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "rows.json").write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_html(output / "report.html", summaries, manifest)
    return output
