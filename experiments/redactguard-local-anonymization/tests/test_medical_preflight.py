from redact_bench.preflight import PREFLIGHT_CASE, _benchmark_probe


def test_medical_preflight_uses_a_valid_profile_and_gold():
    for profile in ("asq_phi", "meddocan_phi", "clinical_ner"):
        probe = _benchmark_probe(profile)
        assert probe.profile == profile
        assert probe.case_id == "__preflight__"
        assert len(probe.text) < 100
        assert len(probe.gold) == 1
        for gold in probe.gold:
            assert probe.text[gold.start:gold.end] == gold.value


def test_original_preflight_unchanged_for_legacy_benchmarks():
    assert _benchmark_probe("financial") == PREFLIGHT_CASE
    assert _benchmark_probe(None) == PREFLIGHT_CASE
