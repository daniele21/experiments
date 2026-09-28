from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

from redact_bench.report import write_html


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def combine_model_runs(
    run_dirs: list[Path],
    *,
    output: Path,
    suite_id: str,
    kind: str,
) -> Path:
    if not run_dirs:
        raise ValueError("No model runs to combine")

    output.mkdir(parents=True, exist_ok=False)
    manifests = [_read_json(path / "manifest.json") for path in run_dirs]
    first_manifest = deepcopy(manifests[0])

    models: list[str] = []
    metrics: dict[str, dict] = {}
    failures: dict[str, list] = {}
    rows: list[dict] = []
    identities: dict[str, dict | None] = {}

    for path, manifest in zip(run_dirs, manifests, strict=True):
        run_models = list(manifest.get("models", []))
        if len(run_models) != 1:
            raise ValueError(f"Expected one model per isolated run: {path}")
        model = run_models[0]
        models.append(model)

        model_metrics = _read_json(path / "metrics.json")
        metrics[model] = model_metrics[model]

        failure_path = path / "failures.json"
        if failure_path.exists():
            failures[model] = _read_json(failure_path).get(model, [])

        rows.extend(_read_json(path / "rows.json"))
        identities[model] = (
            manifest.get("korgis", {})
            .get("runtime_identity", {})
            .get(model)
        )

        raw_path = path / f"{model.replace('/', '_')}.jsonl"
        if raw_path.exists():
            shutil.copy2(raw_path, output / raw_path.name)

    combined = first_manifest
    combined["run_id"] = f"{suite_id}-{kind}"
    combined["suite_id"] = suite_id
    combined["kind"] = kind
    combined["models"] = models
    combined["runtime_strategy"] = "restart_per_model"
    combined.setdefault("korgis", {})["runtime_identity"] = identities

    _write_json(output / "manifest.json", combined)
    _write_json(output / "metrics.json", metrics)
    _write_json(output / "rows.json", rows)
    if failures:
        _write_json(output / "failures.json", failures)
    write_html(output / "report.html", metrics, combined)
    return output
