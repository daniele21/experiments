from redact_bench.postprocess import findings_from_model_payload, resolve_model_payload


def test_model_value_is_applied_to_all_occurrences():
    text = "Mario Rossi parla. Mario Rossi firma."
    payload = {"pii_fields": [{"pii_type": "private_person", "value": "Mario Rossi"}]}
    findings = findings_from_model_payload(text, payload)
    assert [(f.start, f.end) for f in findings] == [(0, 11), (19, 30)]


def test_hallucinated_value_is_not_redacted():
    findings = findings_from_model_payload(
        "Nessun nome qui",
        {"pii_fields": [{"pii_type": "private_person", "value": "Mario Rossi"}]},
    )
    assert findings == []


def test_matching_is_case_sensitive_like_redactguard_v1():
    findings = findings_from_model_payload(
        "Mario Rossi",
        {"pii_fields": [{"pii_type": "private_person", "value": "mario rossi"}]},
    )
    assert findings == []


def test_unresolved_model_value_remains_in_resolution_diagnostics():
    result = resolve_model_payload(
        "Mario Rossi",
        {
            "pii_fields": [
                {"pii_type": "private_person", "value": "Mario Rossi"},
                {"pii_type": "private_person", "value": "Luigi Verdi"},
            ]
        },
    )

    assert len(result.findings) == 1
    assert result.resolved_items == 1
    assert result.unresolved_items == 1
