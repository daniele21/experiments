from __future__ import annotations

import pandas as pd

from benchmark_core.run_identity import RunIdentity

from jev_bench import cli


def test_jev_tag_run_uses_shared_run_identity(monkeypatch) -> None:
    identity = RunIdentity(
        run_id="run-1",
        run_group="group-1",
        suite="smoke",
        run_timestamp_utc="2026-09-27T12:00:00+00:00",
        runner_location="ci",
    )
    monkeypatch.setattr(cli, "create_run_identity", lambda **_: identity)

    tagged = cli._tag_run(
        pd.DataFrame([{"case_id": "case-1", "provider": "fake", "model": "fake-model"}]),
        "group-1",
        "smoke",
    )

    row = tagged.iloc[0]
    assert row["run_id"] == "run-1"
    assert row["run_group"] == "group-1"
    assert row["suite"] == "smoke"
    assert row["run_timestamp_utc"] == "2026-09-27T12:00:00+00:00"
    assert row["runner_location"] == "ci"
