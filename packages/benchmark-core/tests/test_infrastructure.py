from __future__ import annotations

import json
from pathlib import Path

from benchmark_core.manifests import write_environment_manifest
from benchmark_core.persistence import append_csv_records
from benchmark_core.run_identity import create_run_identity


def test_run_identity_can_be_created_deterministically() -> None:
    identity = create_run_identity(
        run_group="group-1",
        suite="smoke",
        runner_location="ci",
        run_id="run-1",
        run_timestamp_utc="2026-09-27T12:00:00+00:00",
    )

    assert identity.run_id == "run-1"
    assert identity.run_group == "group-1"
    assert identity.suite == "smoke"
    assert identity.run_timestamp_utc == "2026-09-27T12:00:00+00:00"
    assert identity.runner_location == "ci"


def test_environment_manifest_preserves_legacy_envelope(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_environment_manifest(
        path,
        run_group="group-1",
        suite="public-budget",
        runner_location="ci",
        requested_models={"api": ["model-a"]},
        resolved_models={"provider-a": ["model-a"]},
        parameters={"seed": 42},
        pricing={"currency": "USD"},
        packages=(),
        created_at_utc="2026-09-27T12:00:00+00:00",
        git_commit_sha="abc123",
        python="3.12.0",
        platform_value="test-platform",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload == {
        "created_at_utc": "2026-09-27T12:00:00+00:00",
        "git_commit": "abc123",
        "packages": {},
        "parameters": {"seed": 42},
        "platform": "test-platform",
        "pricing": {"currency": "USD"},
        "python": "3.12.0",
        "requested_models": {"api": ["model-a"]},
        "resolved_models": {"provider-a": ["model-a"]},
        "run_group": "group-1",
        "runner_location": "ci",
        "suite": "public-budget",
    }



def test_csv_persistence_appends_rows_and_extends_schema(tmp_path: Path) -> None:
    path = tmp_path / "results.csv"

    append_csv_records(
        [{"case_id": "first", "correct": True}],
        path,
        fieldnames=["case_id", "correct"],
    )
    append_csv_records(
        [{"case_id": "second", "correct": False, "latency_ms": 12.5}],
        path,
        fieldnames=["case_id", "correct", "latency_ms"],
    )

    lines = path.read_text(encoding="utf-8").splitlines()

    assert lines == [
        "case_id,correct,latency_ms",
        "first,True,",
        "second,False,12.5",
    ]
