from __future__ import annotations

from dataclasses import asdict

from redact_bench.metrics import EVALUATION_SCHEMA
from redact_bench.models import Case, Span
from redact_bench.provider import KorgisRedactProvider


PREFLIGHT_TEXT = (
    "Cliente Mario Rossi. "
    "Contatto: mario.rossi@example.com. "
    "Telefono: +39 333 1234567."
)


def _span(value: str, pii_type: str) -> Span:
    start = PREFLIGHT_TEXT.index(value)
    return Span(start=start, end=start + len(value), pii_type=pii_type, value=value)


PREFLIGHT_CASE = Case(
    case_id="__preflight__",
    profile="financial",
    text=PREFLIGHT_TEXT,
    gold=(
        _span("Mario Rossi", "private_person"),
        _span("mario.rossi@example.com", "private_email"),
        _span("+39 333 1234567", "private_phone"),
    ),
    tags=("preflight",),
)


def run_model_preflight(provider: KorgisRedactProvider) -> dict:
    """Verify the model/runtime can satisfy the inference contract before scoring."""
    result = provider.evaluate(PREFLIGHT_CASE)
    resolved_values = {finding.value for finding in result.findings}
    expected_values = {span.value for span in PREFLIGHT_CASE.gold}
    return {
        "model": provider.model,
        "passed": result.valid,
        "status": result.status,
        "error_type": result.error_type,
        "error": result.error,
        "http_status": result.http_status,
        "finish_reason": result.finish_reason,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "raw_item_count": result.raw_item_count,
        "resolved_item_count": result.resolved_item_count,
        "unresolved_item_count": result.unresolved_item_count,
        "smoke_detection_pass": bool(resolved_values & expected_values),
        "expected": [asdict(span) for span in PREFLIGHT_CASE.gold],
    }


def contract_failed_summary(preflight: dict, *, planned_cases: int) -> dict:
    micro = {
        "status": "contract_failed",
        "quality_available": False,
        "preflight_passed": False,
        "preflight_status": preflight.get("status"),
        "cases": planned_cases,
        "evaluated_cases": 0,
        "inference_failures": 0,
        "inference_success_rate": None,
        "evaluated_case_coverage": 0.0,
        "valid_output_rate": None,
        "contract_valid_rate": 0.0,
        "truncation_rate": (
            1.0 if preflight.get("status") == "truncated_output" else 0.0
        ),
        "gold_count": None,
        "quality_gold_count": 0,
        "predicted_count": 0,
        "raw_item_count": preflight.get("raw_item_count", 0),
        "resolved_item_count": preflight.get("resolved_item_count", 0),
        "unresolved_item_count": preflight.get("unresolved_item_count", 0),
        "span_resolution_rate": None,
        "tp": 0,
        "exact_tp": 0,
        "fp": 0,
        "fn": 0,
        "pii_recall": None,
        "precision": None,
        "span_f1": None,
        "exact_match_recall": None,
        "leakage_rate": None,
        "zero_leak_document_rate": None,
        "over_redaction_rate": None,
        "leaked_chars": 0,
        "gold_chars": 0,
        "overredacted_chars": 0,
        "non_pii_chars": 0,
        "latency_p50_ms": None,
        "latency_p95_ms": None,
        "latency_p99_ms": None,
        "failures": 0,
        "system_tp": 0,
        "system_fp": 0,
        "system_fn": 0,
        "system_pii_recall": None,
        "system_leakage_rate": None,
        "system_zero_leak_document_rate": None,
        "inference_statuses": {preflight.get("status", "unknown"): 1},
        "errors": (
            {preflight["error_type"]: 1}
            if preflight.get("error_type")
            else {}
        ),
    }
    return {
        **micro,
        "evaluation_schema": EVALUATION_SCHEMA,
        "micro": micro,
        "macro": {},
        "by_type": {},
        "by_profile": {},
        "by_document": {},
        "dataset_balance": {},
        "failure_analysis": [
            {
                "case_id": "__preflight__",
                "profile": "financial",
                "quality_available": False,
                "inference_status": preflight.get("status"),
                "error_type": preflight.get("error_type"),
                "pii_recall": None,
                "precision": None,
                "leakage_rate": None,
                "system_pii_recall": None,
                "system_leakage_rate": None,
                "over_redaction_rate": None,
                "fn": 0,
                "fp": 0,
                "system_fn": 0,
                "inference_failures": 0,
                "unresolved_item_count": preflight.get("unresolved_item_count", 0),
                "false_negatives": [],
                "false_positives": [],
                "error": preflight.get("error"),
            }
        ],
        "preflight": preflight,
    }
