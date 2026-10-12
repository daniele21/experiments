from pathlib import Path

from redact_bench.dataset_audit import audit_cases
from redact_bench.datasets import load_dataset
from redact_bench.profiles import load_profile_snapshot


ROOT = Path(__file__).resolve().parents[1]


def test_ambiguous_challenge_contract():
    cases = load_dataset(ROOT / "data/ambiguous/cases.jsonl")
    assert len(cases) == 48
    assert len({c.case_id for c in cases}) == 48
    assert {c.profile for c in cases} == {"general","financial","healthcare","legal"}  # profile coverage
    by_family = {}
    for case in cases:
        assert case.gold_version == "ambiguous_synthetic_v0.1"
        assert case.human_reviewed is False
        assert "synthetic" in case.tags and "contrast" in case.tags
        assert case.content_family_id is not None
        assert case.variant_id in ("pos", "neg")
        by_family.setdefault(case.content_family_id, []).append(case)
        for span in case.gold:
            assert case.text[span.start:span.end] == span.value
            assert span.pii_subtype is not None
    assert len(by_family) == 24
    for family, group in by_family.items():
        assert {c.variant_id for c in group} == {"pos", "neg"}, family
        assert next(c for c in group if c.variant_id == "pos").gold
        assert not next(c for c in group if c.variant_id == "neg").gold
    snapshot = load_profile_snapshot(ROOT / "config/profiles.yaml")
    audit = audit_cases(cases, snapshot)
    assert audit["positive_cases"] == 24
    assert audit["negative_cases"] == 24
    assert audit["contrast_families"] == 24
    assert audit["human_reviewed_cases"] == 0
    assert audit["largest_case_share"] < 0.10
    assert set(["health_condition","account_number","secret","private_date","private_address","private_url"]) <= set(audit["gold_spans_by_type"])
    for case in cases:
        valid_types = set(snapshot["profiles"][case.profile])
        assert {span.pii_type for span in case.gold} <= valid_types
