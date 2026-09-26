from pathlib import Path

from redact_bench.metrics import aggregate, aggregate_detailed, score_case
from redact_bench.models import Case, Finding, InferenceResult, Span
from redact_bench.report import write_html


def _result(
    *,
    case_id: str,
    findings: list[Finding],
    model: str = "m",
    latency_ms: float = 10,
) -> InferenceResult:
    return InferenceResult(
        case_id=case_id,
        model=model,
        valid=True,
        latency_ms=latency_ms,
        findings=findings,
        raw_content="{}",
    )


def test_perfect_case_has_no_leakage():
    case = Case(
        "x",
        "general",
        "Mario Rossi",
        (Span(0, 11, "private_person", "Mario Rossi"),),
    )
    row = score_case(
        case,
        _result(
            case_id="x",
            findings=[Finding("private_person", "Mario Rossi", 0, 11)],
        ),
    )
    summary = aggregate([row])
    assert summary["pii_recall"] == 1.0
    assert summary["leakage_rate"] == 0.0
    assert summary["zero_leak_document_rate"] == 1.0


def test_evaluation_v2_exposes_micro_macro_and_document_balance():
    large_text = "A" * 200
    large_gold = tuple(
        Span(index * 2, index * 2 + 1, "account_number", "A")
        for index in range(100)
    )
    large = Case("large.xlsx", "financial", large_text, large_gold)
    small = Case(
        "small.txt",
        "financial",
        "Mario",
        (Span(0, 5, "private_person", "Mario"),),
    )

    large_result = _result(
        case_id="large.xlsx",
        findings=[
            Finding("account_number", "A", span.start, span.end)
            for span in large.gold
        ],
    )
    small_result = _result(case_id="small.txt", findings=[])

    detailed = aggregate_detailed(
        [
            score_case(large, large_result),
            score_case(small, small_result),
        ]
    )

    assert detailed["evaluation_schema"] == "redactguard-evaluation-v2"
    assert detailed["micro"]["pii_recall"] == 100 / 101
    assert detailed["macro"]["pii_recall"] == 0.5
    assert detailed["dataset_balance"]["largest_document"] == "large.xlsx"
    assert detailed["dataset_balance"]["largest_document_share"] == 100 / 101
    assert detailed["by_document"]["small.txt"]["fn"] == 1


def test_evaluation_v2_reports_by_type_and_failure_examples():
    case = Case(
        "mixed.txt",
        "financial",
        "Mario mario@example.com",
        (
            Span(0, 5, "private_person", "Mario"),
            Span(6, 23, "private_email", "mario@example.com"),
        ),
    )
    result = _result(
        case_id="mixed.txt",
        findings=[
            Finding("private_person", "Mario", 0, 5),
            Finding("private_phone", "mario@example.com", 6, 23),
        ],
    )

    detailed = aggregate_detailed([score_case(case, result)])

    assert detailed["by_type"]["private_person"]["pii_recall"] == 1.0
    assert detailed["by_type"]["private_email"]["pii_recall"] == 0.0
    assert detailed["by_type"]["private_phone"]["precision"] == 0.0
    failure = detailed["failure_analysis"][0]
    assert failure["case_id"] == "mixed.txt"
    assert failure["false_negatives"][0]["pii_type"] == "private_email"
    assert failure["false_positives"][0]["pii_type"] == "private_phone"


def test_evaluation_v2_html_contains_diagnostic_sections(tmp_path: Path):
    case = Case(
        "x",
        "general",
        "Mario Rossi",
        (Span(0, 11, "private_person", "Mario Rossi"),),
    )
    row = score_case(
        case,
        _result(case_id="x", findings=[]),
    )
    summaries = {"m": aggregate_detailed([row])}
    path = tmp_path / "report.html"

    write_html(path, summaries, {"run_id": "test"})

    content = path.read_text(encoding="utf-8")
    assert "Micro recall" in content
    assert "Macro recall" in content
    assert "Performance by PII type" in content
    assert "Performance by document" in content
    assert "Failure analysis" in content
