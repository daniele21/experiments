from __future__ import annotations

from collections import Counter, defaultdict
import hashlib

from redact_bench.models import Case


def audit_cases(cases: list[Case], profile_snapshot: dict | None = None) -> dict:
    by_profile: Counter[str] = Counter(case.profile for case in cases)
    by_type: Counter[str] = Counter()
    by_subtype: Counter[str] = Counter()
    by_family: Counter[str] = Counter()
    gold_by_case: dict[str, int] = {}
    gold_by_family: Counter[str] = Counter()
    reviewed = 0
    hashes: dict[str, list[str]] = defaultdict(list)
    family_polarity: dict[str, set[str]] = defaultdict(set)

    for case in cases:
        family = case.content_family_id or case.case_id
        by_family[family] += 1
        gold_count = len(case.gold)
        gold_by_case[case.case_id] = gold_count
        gold_by_family[family] += gold_count
        if case.human_reviewed:
            reviewed += 1

        digest = hashlib.sha256(case.text.encode("utf-8")).hexdigest()
        hashes[digest].append(case.case_id)

        if gold_count:
            family_polarity[family].add("positive")
        else:
            family_polarity[family].add("negative")

        for span in case.gold:
            by_type[span.pii_type] += 1
            if span.pii_subtype:
                by_subtype[f"{span.pii_type}:{span.pii_subtype}"] += 1

    total_gold = sum(gold_by_case.values())
    largest_case = max(gold_by_case, key=gold_by_case.get) if gold_by_case else None
    largest_family = (
        max(gold_by_family, key=gold_by_family.get) if gold_by_family else None
    )

    expected_by_profile: dict[str, set[str]] = {}
    if profile_snapshot:
        for profile, definitions in profile_snapshot.get("profiles", {}).items():
            expected_by_profile[str(profile)] = set(definitions)

    covered_by_profile: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        for span in case.gold:
            covered_by_profile[case.profile].add(span.pii_type)

    profile_coverage = {}
    for profile in sorted(set(by_profile) | set(expected_by_profile)):
        expected = expected_by_profile.get(profile, set())
        covered = covered_by_profile.get(profile, set())
        profile_coverage[profile] = {
            "cases": by_profile.get(profile, 0),
            "expected_types": sorted(expected),
            "covered_types": sorted(covered),
            "missing_types": sorted(expected - covered),
            "coverage_rate": (
                len(covered & expected) / len(expected)
                if expected
                else None
            ),
        }

    expected_union = set().union(*expected_by_profile.values()) if expected_by_profile else set()
    covered_union = set(by_type)

    return {
        "cases": len(cases),
        "content_families": len(by_family),
        "positive_cases": sum(1 for count in gold_by_case.values() if count > 0),
        "negative_cases": sum(1 for count in gold_by_case.values() if count == 0),
        "contrast_families": sum(
            polarity == {"positive", "negative"}
            for polarity in family_polarity.values()
        ),
        "human_reviewed_cases": reviewed,
        "human_reviewed_rate": reviewed / len(cases) if cases else 0.0,
        "gold_spans": total_gold,
        "gold_spans_by_type": dict(sorted(by_type.items())),
        "gold_spans_by_subtype": dict(sorted(by_subtype.items())),
        "cases_by_profile": dict(sorted(by_profile.items())),
        "cases_by_family": dict(sorted(by_family.items())),
        "gold_spans_by_family": dict(sorted(gold_by_family.items())),
        "largest_case": largest_case,
        "largest_case_gold_spans": gold_by_case.get(largest_case, 0) if largest_case else 0,
        "largest_case_share": (
            gold_by_case[largest_case] / total_gold
            if largest_case and total_gold
            else 0.0
        ),
        "largest_family": largest_family,
        "largest_family_gold_spans": (
            gold_by_family.get(largest_family, 0) if largest_family else 0
        ),
        "largest_family_share": (
            gold_by_family[largest_family] / total_gold
            if largest_family and total_gold
            else 0.0
        ),
        "duplicate_text_groups": [
            ids for ids in hashes.values() if len(ids) > 1
        ],
        "taxonomy": {
            "expected_types": sorted(expected_union),
            "covered_types": sorted(covered_union),
            "missing_types": sorted(expected_union - covered_union),
            "coverage_rate": (
                len(covered_union & expected_union) / len(expected_union)
                if expected_union
                else None
            ),
            "by_profile": profile_coverage,
        },
    }
