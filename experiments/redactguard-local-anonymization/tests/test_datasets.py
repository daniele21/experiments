from pathlib import Path

from redact_bench.dataset_audit import audit_cases
from redact_bench.datasets import load_jsonl
from redact_bench.profiles import load_profile_snapshot


def test_smoke_dataset_loads():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/smoke/cases.jsonl")
    assert len(cases) == 20
    repeated = next(case for case in cases if case.case_id == "g03")
    assert len(repeated.gold) == 2


def test_load_dataset_filter_by_id():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/smoke/cases.jsonl")
    by_id = {c.case_id: c for c in cases}
    selected = [by_id[cid] for cid in ["g01", "g03"] if cid in by_id]
    assert len(selected) == 2
    assert [c.case_id for c in selected] == ["g01", "g03"]



def test_challenge_dataset_covers_full_taxonomy():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/challenge/cases.jsonl")
    assert len(cases) == 46

    covered_types = {
        span.pii_type
        for case in cases
        for span in case.gold
    }
    expected = {
        "private_person",
        "private_email",
        "private_phone",
        "private_address",
        "private_date",
        "private_url",
        "account_number",
        "personal_demographic",
        "secret",
        "health_condition",
        "health_treatment",
        "health_lab_result",
        "personal_measurement",
        "lifestyle_info",
    }
    assert covered_types == expected
    assert all(case.content_family_id for case in cases)
    assert all(case.gold_version == "challenge_v0.1" for case in cases)
    assert all(case.human_reviewed is False for case in cases)


def test_challenge_dataset_contains_contrast_families():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/challenge/cases.jsonl")
    by_family = {}
    for case in cases:
        by_family.setdefault(case.content_family_id, []).append(case)

    contrast_families = [
        family_cases
        for family_cases in by_family.values()
        if {tag for case in family_cases for tag in case.tags} >= {"positive", "negative"}
    ]
    assert len(contrast_families) >= 15


def test_challenge_audit_reports_full_taxonomy_and_contrast_pairs():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/challenge/cases.jsonl")
    snapshot = load_profile_snapshot(root / "config/profiles.yaml")

    audit = audit_cases(cases, snapshot)

    assert audit["taxonomy"]["missing_types"] == []
    assert audit["taxonomy"]["coverage_rate"] == 1.0
    assert audit["contrast_families"] >= 15
    assert audit["negative_cases"] >= 15
    assert audit["human_reviewed_rate"] == 0.0
