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



def test_banking_subset_is_reproducible_for_same_seed(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_fixture(cache)

    first = balanced_banking77_cases(cache, max_cases=4, seed=7)
    second = balanced_banking77_cases(cache, max_cases=4, seed=7)

    assert [
        (case.case_id, case.state, case.expected, case.metadata)
        for case in first
    ] == [
        (case.case_id, case.state, case.expected, case.metadata)
        for case in second
    ]


def test_banking_subset_preserves_historical_seeded_order(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_fixture(cache)

    cases = balanced_banking77_cases(cache, max_cases=4, seed=7)

    assert [
        (case.case_id, case.state, case.expected["intent"])
        for case in cases
    ] == [
        ("banking77-card_arrival-1", "where is my card 0", "card_arrival"),
        (
            "banking77-cash_withdrawal-1",
            "cash withdrawal issue 0",
            "cash_withdrawal",
        ),
        (
            "banking77-cash_withdrawal-0",
            "cash withdrawal issue 2",
            "cash_withdrawal",
        ),
        ("banking77-card_arrival-0", "where is my card 2", "card_arrival"),
    ]


def test_public_dataset_revisions_come_from_catalog(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_fixture(cache)

    banking = balanced_banking77_cases(cache, max_cases=1, seed=1)
    calibration = calibration_public_cases(
        cache,
        in_scope_cases=1,
        oos_cases=1,
        seed=1,
    )

    assert banking[0].metadata["dataset_revision"] == (
        "9d081458ff52e53cf7e848f414e6e9344e4e6696"
    )
    clinc = next(
        case for case in calibration
        if case.metadata["difficulty"] == "out_of_scope"
    )
    assert clinc.metadata["dataset_revision"] == (
        "48a0e1cff8f43dd4d0836ecb4ed5df08733e3d2e"
    )
