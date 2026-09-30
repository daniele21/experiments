from types import SimpleNamespace
from redact_bench.models import Case, Finding, InferenceResult
from redact_bench.resilient_evaluator import (
    ResilientExecutionSettings,
    clean_exception_details,
    evaluate_case_resiliently,
    is_density_failure,
)
from redact_bench.segmentation import TextSegment


def test_is_density_failure_detection():
    # Valid result is never a failure
    valid_res = InferenceResult("c", "m", valid=True, latency_ms=10.0, findings=[], raw_content="")
    assert is_density_failure(valid_res) is False

    # Timeout failure
    timeout_res = InferenceResult(
        "c", "m", valid=False, latency_ms=120000.0, findings=[], raw_content="",
        status="transport_error", error_type="APITimeoutError", error="Request timed out.",
    )
    assert is_density_failure(timeout_res) is True

    # Truncated output
    truncated_res = InferenceResult(
        "c", "m", valid=False, latency_ms=100.0, findings=[], raw_content="",
        status="truncated_output", finish_reason="length",
    )
    assert is_density_failure(truncated_res) is True

    # 502 invalid_model_output
    backend_502_res = InferenceResult(
        "c", "m", valid=False, latency_ms=100.0, findings=[], raw_content="",
        status="backend_error", http_status=502,
        error="InternalServerError: Error code: 502 - Model returned invalid JSON",
    )
    assert is_density_failure(backend_502_res) is True

    # Unrelated error (e.g. 404 not found)
    other_error = InferenceResult(
        "c", "m", valid=False, latency_ms=10.0, findings=[], raw_content="",
        status="backend_error", http_status=404, error="Model not found",
    )
    assert is_density_failure(other_error) is False


def test_clean_exception_details_formatting():
    # Timeout
    timeout_exc = TimeoutError("Connection timed out")
    msg, status, code = clean_exception_details(timeout_exc, 360.0)
    assert "timed out after 360s" in msg
    assert status == "transport_error"

    # Typed Korgis 502 error with line & column details
    exc_502 = SimpleNamespace(
        status_code=502,
        body={
            "detail": {
                "code": "invalid_model_output",
                "message": "Model returned invalid JSON",
                "details": {"format": "json_object", "line": 517, "column": 16},
            }
        },
    )
    msg, status, code = clean_exception_details(exc_502, 360.0)
    assert "line 517, column 16" in msg
    assert status == "backend_error"
    assert code == 502


def test_adaptive_subdivision_recovers_dense_segment():
    # Text with 40 characters:
    # "Chunk 1 content here. Chunk 2 content here."
    text = "Alpha Mario Rossi Beta. Gamma Luigi Verdi Delta."

    # Mock evaluator: fails if segment text > 30 chars, succeeds if <= 30 chars
    def mock_evaluator(case: Case, segment: TextSegment) -> InferenceResult:
        if len(segment.text) > 30:
            return InferenceResult(
                case_id=case.case_id,
                model="test-model",
                valid=False,
                latency_ms=100.0,
                findings=[],
                raw_content="",
                status="backend_error",
                http_status=502,
                error="InternalServerError: 502 - Model returned invalid JSON",
            )
        findings = []
        if "Mario Rossi" in segment.text:
            idx = segment.text.index("Mario Rossi")
            findings.append(Finding(pii_type="private_person", value="Mario Rossi", start=idx, end=idx + 11))
        if "Luigi Verdi" in segment.text:
            idx = segment.text.index("Luigi Verdi")
            findings.append(Finding(pii_type="private_person", value="Luigi Verdi", start=idx, end=idx + 11))
        return InferenceResult(
            case_id=case.case_id,
            model="test-model",
            valid=True,
            latency_ms=50.0,
            findings=findings,
            raw_content="{}",
            status="success",
            finish_reason="stop",
        )

    case = Case(case_id="dense", profile="general", text=text, gold=())
    settings = ResilientExecutionSettings(
        chunk_max_chars=50,
        chunk_overlap_chars=8,
        adaptive_subdivision=True,
        min_split_chars=20,
    )

    result = evaluate_case_resiliently(
        case,
        model="test-model",
        evaluator=mock_evaluator,
        settings=settings,
    )

    # Adaptive subdivision split the 48-char segment in half and both succeeded!
    assert result.valid is True
    assert len(result.findings) == 2
    assert result.findings[0].value == "Mario Rossi"
    assert result.findings[1].value == "Luigi Verdi"
    assert text[result.findings[0].start : result.findings[0].end] == "Mario Rossi"
    assert text[result.findings[1].start : result.findings[1].end] == "Luigi Verdi"


def test_preserves_partial_findings_on_hard_failure():
    text = "First segment with Mario Rossi. Second segment with error."

    # Segment 1 succeeds, segment 2 fails
    def mock_evaluator(case: Case, segment: TextSegment) -> InferenceResult:
        if segment.start == 0:
            idx = segment.text.index("Mario Rossi")
            return InferenceResult(
                case_id=case.case_id,
                model="test-model",
                valid=True,
                latency_ms=30.0,
                findings=[Finding(pii_type="private_person", value="Mario Rossi", start=idx, end=idx + 11)],
                raw_content="{}",
                status="success",
            )
        return InferenceResult(
            case_id=case.case_id,
            model="test-model",
            valid=False,
            latency_ms=10.0,
            findings=[],
            raw_content="",
            status="backend_error",
            http_status=500,
            error="Non-retryable backend crash",
        )

    case = Case(case_id="partial", profile="general", text=text, gold=())
    settings = ResilientExecutionSettings(
        chunk_max_chars=32,
        chunk_overlap_chars=4,
        adaptive_subdivision=False,
    )

    result = evaluate_case_resiliently(
        case,
        model="test-model",
        evaluator=mock_evaluator,
        settings=settings,
    )

    assert result.valid is False
    assert result.successful_segments == 1
    # Findings from segment 1 are preserved
    assert len(result.findings) == 1
    assert result.findings[0].value == "Mario Rossi"
    assert text[result.findings[0].start : result.findings[0].end] == "Mario Rossi"
