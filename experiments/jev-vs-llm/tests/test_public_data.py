import csv
import json
from pathlib import Path

from jev_bench.benchmark_data import (
    balanced_banking77_cases,
    calibration_public_cases,
)


def _write_fixture(cache: Path) -> None:
    banking = cache / "banking77"
    banking.mkdir(parents=True)
    (banking / "categories.json").write_text(
        json.dumps(["card_arrival", "cash_withdrawal"]),
        encoding="utf-8",
    )
    with (banking / "test.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "category"])
        for i in range(3):
            writer.writerow([f"where is my card {i}", "card_arrival"])
            writer.writerow([f"cash withdrawal issue {i}", "cash_withdrawal"])

    clinc = cache / "clinc150"
    clinc.mkdir(parents=True)
    (clinc / "data_full.json").write_text(
        json.dumps(
            {
                "oos_test": [
                    ["what is the weather tomorrow", "oos"],
                    ["how do i cook pasta", "oos"],
                    ["what is my bank balance", "oos"],
                ]
            }
        ),
        encoding="utf-8",
    )


def test_balanced_banking_subset_has_exact_requested_size(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_fixture(cache)

    cases = balanced_banking77_cases(cache, max_cases=3, seed=1)

    assert len(cases) == 3
    assert {case.expected["intent"] for case in cases} == {
        "card_arrival",
        "cash_withdrawal",
    }


def test_full_calibration_matches_in_scope_to_filtered_oos(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_fixture(cache)

    cases = calibration_public_cases(
        cache,
        in_scope_cases=None,
        oos_cases=None,
        seed=1,
    )

    oos = [case for case in cases if case.metadata["difficulty"] == "out_of_scope"]
    in_scope = [case for case in cases if case.metadata["difficulty"] == "in_scope"]

    assert len(oos) == 2
    assert len(in_scope) == 2
    assert all(case.expected["intent"] == "other" for case in oos)
