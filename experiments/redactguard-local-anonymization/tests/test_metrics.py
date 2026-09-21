from redact_bench.metrics import aggregate, score_case
from redact_bench.models import Case, Finding, InferenceResult, Span


def test_perfect_case_has_no_leakage():
    case = Case("x", "general", "Mario Rossi", (Span(0, 11, "private_person", "Mario Rossi"),))
    result = InferenceResult(
        case_id="x",
        model="m",
        valid=True,
        latency_ms=10,
        findings=[Finding("private_person", "Mario Rossi", 0, 11)],
        raw_content="{}",
    )
    row = score_case(case, result)
    summary = aggregate([row])
    assert summary["pii_recall"] == 1.0
    assert summary["leakage_rate"] == 0.0
    assert summary["zero_leak_document_rate"] == 1.0
