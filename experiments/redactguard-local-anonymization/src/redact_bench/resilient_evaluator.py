"""Resilient evaluation and adaptive segmentation engine for local LLMs.

This module provides adaptive sub-segmentation and robust error recovery
when evaluating realistic documents with high PII density or complex layouts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from redact_bench.models import Case, Finding, InferenceResult
from redact_bench.segmentation import TextSegment, segment_text


@dataclass(frozen=True)
class ResilientExecutionSettings:
    """Execution parameters controlling segmentation, timeouts, and adaptive retries."""

    timeout_seconds: float = 360.0
    chunk_max_chars: int = 4000
    chunk_overlap_chars: int = 256
    max_output_tokens: int = 4096
    adaptive_subdivision: bool = True
    min_split_chars: int = 400
    max_subdivision_depth: int = 3


def is_density_failure(result: InferenceResult) -> bool:
    """Detect whether a segment failure is due to token exhaustion, timeout, or broken JSON syntax."""
    if result.valid:
        return False

    error_lower = (result.error or "").lower()
    error_type_lower = (result.error_type or "").lower()

    if result.status == "truncated_output" or result.finish_reason in {"length", "max_tokens"}:
        return True

    if result.status == "transport_error" and ("timeout" in error_lower or "timeout" in error_type_lower):
        return True

    if result.status == "backend_error" and (
        result.http_status == 502 or "invalid_model_output" in error_lower
    ):
        return True

    if result.status in {"invalid_json", "invalid_response"} or "jsondecodeerror" in error_type_lower:
        return True

    return False


def clean_exception_details(exc: Exception, timeout_seconds: float) -> tuple[str, str, int | None]:
    """Extract clean, structured error description, status, and HTTP code from API exceptions."""
    status_code = getattr(exc, "status_code", None)
    error_type = type(exc).__name__
    lowered = error_type.lower()
    raw_message = str(exc)

    if "timeout" in lowered or "connection" in lowered:
        status = "transport_error"
        error_msg = f"{error_type}: Request timed out after {timeout_seconds:.0f}s."
        return error_msg, status, status_code

    # Extract typed Korgis invalid_model_output details if present
    if status_code == 502 or "invalid_model_output" in raw_message:
        status = "backend_error"
        try:
            body = getattr(exc, "body", None)
            if isinstance(body, dict) and "detail" in body:
                details = body["detail"].get("details", {})
                line = details.get("line")
                col = details.get("column")
                if line is not None and col is not None:
                    return (
                        f"InternalServerError: 502 - Model returned invalid JSON (line {line}, column {col})",
                        status,
                        502,
                    )
        except Exception:
            pass

    status = "backend_error" if status_code is not None else "provider_error"
    return f"{error_type}: {exc}", status, status_code


def _add_optional(current: int | None, addition: int | None) -> int | None:
    if current is None and addition is None:
        return None
    return (current or 0) + (addition or 0)


def evaluate_segment_with_subdivision(
    case: Case,
    segment: TextSegment,
    *,
    evaluator: Callable[[Case, TextSegment], InferenceResult],
    settings: ResilientExecutionSettings,
    depth: int = 0,
) -> InferenceResult:
    """Evaluate a text segment, recursively splitting into sub-segments on density failures."""
    local_case = Case(
        case_id=case.case_id,
        profile=case.profile,
        text=segment.text,
        gold=(),
        tags=case.tags,
    )
    result = evaluator(local_case, segment)

    if result.valid:
        return result

    # For syntax errors (502 / invalid JSON), fail fast by limiting retry depth to 1
    is_syntax_error = result.status == "backend_error" and (
        result.http_status == 502 or "invalid_model_output" in (result.error or "").lower()
    )
    effective_max_depth = 1 if is_syntax_error else settings.max_subdivision_depth

    can_subdivide = (
        settings.adaptive_subdivision
        and is_density_failure(result)
        and len(segment.text) >= settings.min_split_chars
        and depth < effective_max_depth
    )

    if not can_subdivide:
        return result

    # Subdivide segment into two halves preserving token overlap
    half_chars = max(settings.min_split_chars // 2, len(segment.text) // 2)
    sub_pieces = segment_text(
        segment.text,
        max_chars=half_chars + settings.chunk_overlap_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )

    if len(sub_pieces) <= 1:
        return result

    sub_findings: list[Finding] = []
    seen: set[tuple[int, int, str]] = set()
    total_latency_ms = result.latency_ms
    input_tokens = result.input_tokens
    output_tokens = result.output_tokens
    raw_item_count = 0
    resolved_item_count = 0
    unresolved_item_count = 0

    for sub_idx, sub in enumerate(sub_pieces):
        # Global segment referencing the full document
        global_sub = TextSegment(
            start=segment.start + sub.start,
            end=segment.start + sub.end,
            text=sub.text,
        )
        sub_res = evaluate_segment_with_subdivision(
            case=case,
            segment=global_sub,
            evaluator=evaluator,
            settings=settings,
            depth=depth + 1,
        )

        total_latency_ms += sub_res.latency_ms
        input_tokens = _add_optional(input_tokens, sub_res.input_tokens)
        output_tokens = _add_optional(output_tokens, sub_res.output_tokens)
        raw_item_count += sub_res.raw_item_count
        resolved_item_count += sub_res.resolved_item_count
        unresolved_item_count += sub_res.unresolved_item_count

        if not sub_res.valid:
            # Propagate sub-segment failure
            return InferenceResult(
                case_id=case.case_id,
                model=result.model,
                valid=False,
                latency_ms=total_latency_ms,
                findings=sub_findings,
                raw_content=sub_res.raw_content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=f"sub-segment {sub_idx + 1}/{len(sub_pieces)}: {sub_res.error}",
                status=sub_res.status,
                error_type=sub_res.error_type,
                http_status=sub_res.http_status,
                finish_reason=sub_res.finish_reason,
                raw_item_count=raw_item_count,
                resolved_item_count=resolved_item_count,
                unresolved_item_count=unresolved_item_count,
                segment_count=len(sub_pieces),
                successful_segments=sub_idx,
                failed_segment_index=sub_idx,
            )

        for finding in sub_res.findings:
            local_start = sub.start + finding.start
            local_end = sub.start + finding.end
            mapped_finding = Finding(
                pii_type=finding.pii_type,
                value=segment.text[local_start:local_end],
                start=local_start,
                end=local_end,
                field_name=finding.field_name,
                field_description=finding.field_description,
            )
            key = (mapped_finding.start, mapped_finding.end, mapped_finding.pii_type)
            if key not in seen:
                seen.add(key)
                sub_findings.append(mapped_finding)

    return InferenceResult(
        case_id=case.case_id,
        model=result.model,
        valid=True,
        latency_ms=total_latency_ms,
        findings=sorted(sub_findings, key=lambda f: (f.start, f.end, f.pii_type)),
        raw_content=result.raw_content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status="success",
        finish_reason="stop",
        raw_item_count=raw_item_count,
        resolved_item_count=resolved_item_count,
        unresolved_item_count=unresolved_item_count,
        segment_count=len(sub_pieces),
        successful_segments=len(sub_pieces),
    )


def evaluate_case_resiliently(
    case: Case,
    *,
    model: str,
    evaluator: Callable[[Case, TextSegment], InferenceResult],
    settings: ResilientExecutionSettings,
) -> InferenceResult:
    """Run full bounded segmentation on a case, with adaptive subdivision and partial finding retention."""
    segments = segment_text(
        case.text,
        max_chars=settings.chunk_max_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )

    if len(segments) == 1:
        single_res = evaluate_segment_with_subdivision(
            case=case,
            segment=segments[0],
            evaluator=evaluator,
            settings=settings,
        )
        single_res.segment_count = 1
        single_res.successful_segments = 1 if single_res.valid else 0
        single_res.failed_segment_index = None if single_res.valid else 0
        return single_res

    total_latency_ms = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_item_count = 0
    resolved_item_count = 0
    unresolved_item_count = 0
    findings: list[Finding] = []
    seen: set[tuple[int, int, str]] = set()
    raw_segments: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        seg_res = evaluate_segment_with_subdivision(
            case=case,
            segment=segment,
            evaluator=evaluator,
            settings=settings,
        )

        total_latency_ms += seg_res.latency_ms
        input_tokens = _add_optional(input_tokens, seg_res.input_tokens)
        output_tokens = _add_optional(output_tokens, seg_res.output_tokens)
        raw_segments.append(
            {
                "index": index,
                "start": segment.start,
                "end": segment.end,
                "status": seg_res.status,
                "finish_reason": seg_res.finish_reason,
                "content": seg_res.raw_content,
                "error_type": seg_res.error_type,
                "error": seg_res.error,
            }
        )

        if not seg_res.valid:
            # Preserve accumulated findings from prior successful segments for transparent diagnostics
            return InferenceResult(
                case_id=case.case_id,
                model=model,
                valid=False,
                latency_ms=total_latency_ms,
                findings=sorted(findings, key=lambda item: (item.start, item.end, item.pii_type)),
                raw_content=json.dumps(raw_segments, ensure_ascii=False),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=(
                    f"segment {index + 1}/{len(segments)}: {seg_res.error}"
                    if seg_res.error
                    else f"segment {index + 1}/{len(segments)} failed"
                ),
                status=seg_res.status,
                error_type=seg_res.error_type,
                http_status=seg_res.http_status,
                finish_reason=seg_res.finish_reason,
                raw_item_count=raw_item_count + seg_res.raw_item_count,
                resolved_item_count=resolved_item_count + seg_res.resolved_item_count,
                unresolved_item_count=unresolved_item_count + seg_res.unresolved_item_count,
                segment_count=len(segments),
                successful_segments=index,
                failed_segment_index=index,
            )

        raw_item_count += seg_res.raw_item_count
        resolved_item_count += seg_res.resolved_item_count
        unresolved_item_count += seg_res.unresolved_item_count

        for finding in seg_res.findings:
            global_start = segment.start + finding.start
            global_end = segment.start + finding.end
            global_finding = Finding(
                pii_type=finding.pii_type,
                value=case.text[global_start:global_end],
                start=global_start,
                end=global_end,
                field_name=finding.field_name,
                field_description=finding.field_description,
            )
            key = (global_finding.start, global_finding.end, global_finding.pii_type)
            if key not in seen:
                seen.add(key)
                findings.append(global_finding)

    return InferenceResult(
        case_id=case.case_id,
        model=model,
        valid=True,
        latency_ms=total_latency_ms,
        findings=sorted(findings, key=lambda item: (item.start, item.end, item.pii_type)),
        raw_content=json.dumps(raw_segments, ensure_ascii=False),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status="success",
        finish_reason="stop",
        raw_item_count=raw_item_count,
        resolved_item_count=resolved_item_count,
        unresolved_item_count=unresolved_item_count,
        segment_count=len(segments),
        successful_segments=len(segments),
    )
