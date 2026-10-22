from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from benchmark_core import read_jsonl_records, sha256_file

from model_capability_bench.analytics.dashboard_export import export_dashboard_data
from model_capability_bench.analytics.projector import project_results
from model_capability_bench.runner.consolidation import consolidate_runs
from model_capability_bench.suite import load_capability_suite

ROOT = Path(__file__).resolve().parents[1]
MODEL = "lfm2.5-24b-a2b-ud-q3-k-xl"
CAP = "mathematical-reasoning"


def _source(base: Path, name: str, samples: list[tuple[str, bool]], *, tokens: int, day: int) -> Path:
    from benchmark_core import to_jsonable

    cap = next(c.spec for c in load_capability_suite(ROOT).resolved_capabilities if c.spec.capability_id == CAP)
    path = base / "runs" / name
    path.mkdir(parents=True)
    stamp = f"2026-10-{day:02d}T10:00:00+00:00"
    manifest = {
        "suite": {"suite_id": "capability-core", "version": "3", "profile": "core", "seed": 42},
        "run": {"run_id": name, "run_group": "test", "planned_cases": len(samples),
                "completed_cases": len(samples), "failed_cases": 0, "metadata": {"signatures": {
                    "models": {MODEL: "model-signature"}, "executions": {MODEL: "execution-signature"},
                    "benchmarks": {CAP: f"benchmark-{tokens}"},
                }}},
        "created_at_utc": stamp,
        "models": [{"model_key": MODEL, "model_id": "vendor/model", "model_signature": "model-signature",
                    "execution_signature": "execution-signature", "deployment": "local"}],
        "capabilities": [{"capability_id": CAP, "task_id": cap.task_id, "dataset_ids": list(cap.dataset_ids),
                          "metrics": [{k: v for k, v in to_jsonable(m).items() if k != "options"}
                                      for m in cap.metrics]}],
    }
    states, raw, evaluations = [], [], []
    for sample, valid in samples:
        cid = f"case-{sample}-{tokens}"
        meta = {"model_key": MODEL, "capability_id": CAP, "dataset_id": "math-reasoning-controlled-v3",
                "dataset_revision": "v3", "dataset_split": "controlled", "sample_id": sample,
                "model_signature": "model-signature", "execution_signature": "execution-signature",
                "benchmark_signature": f"benchmark-{tokens}", "run_id": name,
                "run_group": "test", "valid": valid}
        identity = {**meta, "task_id": CAP, "task_version": "1", "prompt_id": "math", "prompt_version": "1",
                    "suite_id": "capability-core", "suite_version": "3", "generation": {"max_output_tokens": tokens}}
        state = {"case_id": cid, "attempt": 1, "timestamp_utc": stamp,
                 "status": "completed", "metadata": meta, "identity": identity}
        states.append(state)
        record = {"run_id": name, "sample_id": sample, "valid": valid, "model_id": "vendor/model",
                  "task_id": CAP, "input_tokens": 10, "output_tokens": tokens, "latency_ms": 100,
                  "normalized_output": {"answer": "1"}, "raw_output": {"answer": "1"}}
        raw.append({**state, "record": record})
        evaluations.append({**state, "record": {
            "run_id": name, "sample_id": sample, "task_id": CAP, "valid": valid,
            "expected": "1", "prediction": "1" if valid else None,
            "metrics": [{"name": "final_answer_accuracy", "value": int(valid), "primary": True}],
        }})
    (path / "run_manifest.json").write_text(json.dumps(manifest))
    for filename, rows in (("state.jsonl", states), ("raw.jsonl", raw), ("evaluation.jsonl", evaluations)):
        (path / filename).write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def test_latest_attempt_merge_recalculates_metrics_and_preserves_sources(tmp_path: Path) -> None:
    base = _source(tmp_path, "base", [("a", False), ("b", True), ("c", True)], tokens=2048, day=21)
    retry = _source(tmp_path, "retry", [("a", True), ("b", False)], tokens=4096, day=22)
    sources = [base, retry]
    hashes = {p: sha256_file(p) for source in sources for p in source.iterdir()}
    output = tmp_path / "runs" / "merged"
    args = {"sources": sources, "output_dir": output, "run_id": "merged", "run_group": "test",
            "suite": load_capability_suite(ROOT)}
    preview = consolidate_runs(**args, plan_only=True)
    assert not output.exists()
    assert preview["planned_cases"] == 3
    assert preview["invalid_cases"] == 1
    summary = consolidate_runs(**args)
    assert summary["mixed_generation"] is True
    assert summary["failure_rate"] == pytest.approx(1 / 3)
    raw = read_jsonl_records(output / "raw.jsonl")
    evaluation = read_jsonl_records(output / "evaluation.jsonl")
    assert len(raw) == len(evaluation) == 3
    assert {r["record"]["sample_id"]: r["record"]["valid"] for r in raw} == {
        "a": True, "b": False, "c": True,
    }
    assert all(r["metadata"]["consolidation_source"]["run_id"] == "retry" for r in raw
               if r["record"]["sample_id"] in {"a", "b"})
    primary = next(r for r in read_jsonl_records(output / "aggregates.jsonl") if r["primary"])
    assert primary["value"] == pytest.approx(2 / 3)
    assert primary["sample_count"] == 3
    assert all(sha256_file(p) == digest for p, digest in hashes.items())
    # Source ordering has no effect on selected attempts or signatures.
    other = tmp_path / "runs" / "other"
    consolidate_runs(**{**args, "sources": list(reversed(sources)), "output_dir": other, "run_id": "other"})
    assert json.loads((other / "run_manifest.json").read_text())["signatures"] == json.loads(
        (output / "run_manifest.json").read_text())["signatures"]
    with pytest.raises(ValueError, match="already exists"):
        consolidate_runs(**args)


def test_consolidated_projection_updates_latest_but_keeps_canonical_separate(tmp_path: Path) -> None:
    source = _source(tmp_path, "source", [("a", True), ("b", False)], tokens=2048, day=21)
    output = tmp_path / "runs" / "merged"
    consolidate_runs(sources=[source], output_dir=output, run_id="merged", run_group="test",
                     suite=load_capability_suite(ROOT))
    projected = project_results(results_root=tmp_path, rebuild=True, run_dirs=(output,))
    assert projected.projected_runs == 1
    with duckdb.connect(projected.database_path, read_only=True) as db:
        assert db.execute("SELECT COUNT(*) FROM v_current_quality_results").fetchone()[0] == 0
        assert db.execute("SELECT run_id FROM v_latest_quality_results").fetchall() == [("merged",)]
    exported = export_dashboard_data(database_path=Path(projected.database_path), output_dir=tmp_path / "dashboard")
    overview = json.loads(Path(exported["overview"]).read_text())
    public = json.loads(Path(exported["bundle"]).read_text())
    assert public["overview"]["decision"]["model_summaries"] == overview["decision"]["model_summaries"]
    assert public["runs"]["merged"]["run"]["source_dir"] is None
    model = overview["decision"]["model_summaries"][0]
    assert model["observed_case_count"] == 2
    assert model["failure_rate"] == 0.5
    assert model["result_policy"] == "consolidated-latest-attempt"
    assert overview["consolidations"][0]["run_id"] == "merged"
    export_dashboard_data(database_path=Path(projected.database_path), output_dir=tmp_path / "standard", result_view="standard")
    assert json.loads((tmp_path / "standard" / "overview.json").read_text())["cells"] == []


def test_incomplete_latest_attempt_cannot_fall_back_to_success(tmp_path: Path) -> None:
    source = _source(tmp_path, "source", [("a", True)], tokens=2048, day=21)
    row = json.loads((source / "state.jsonl").read_text())
    row.update({"status": "failed", "timestamp_utc": "2026-10-22T10:00:00+00:00", "attempt": 2})
    with (source / "state.jsonl").open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="incomplete or lacks paired"):
        consolidate_runs(sources=[source], output_dir=tmp_path / "merged", run_id="merged",
                         run_group="test", suite=load_capability_suite(ROOT))


@pytest.mark.parametrize("change", ["profile", "artifact", "revision"])
def test_incompatible_sources_are_rejected_before_writing(tmp_path: Path, change: str) -> None:
    first = _source(tmp_path, "first", [("a", True)], tokens=2048, day=21)
    second = _source(tmp_path, "second", [("a", False)], tokens=4096, day=22)
    manifest_file = second / "run_manifest.json"
    manifest = json.loads(manifest_file.read_text())
    if change == "profile":
        manifest["suite"]["profile"] = "smoke"
    elif change == "artifact":
        manifest["models"][0]["model_signature"] = "different-artifact"
    else:
        state_file = second / "state.jsonl"
        row = json.loads(state_file.read_text())
        row["identity"]["dataset_revision"] = "v4"
        state_file.write_text(json.dumps(row) + "\n")
    manifest_file.write_text(json.dumps(manifest))
    output = tmp_path / "merged"
    with pytest.raises(ValueError):
        consolidate_runs(sources=[first, second], output_dir=output, run_id="merged",
                         run_group="test", suite=load_capability_suite(ROOT))
    assert not output.exists()
