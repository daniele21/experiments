from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Iterable

from redact_bench.models import Case, InferenceResult, Span


EVALUATION_SCHEMA = "redactguard-evaluation-v3"


def _predicted_spans(result: InferenceResult) -> list[Span]:
    return [Span(f.start, f.end, f.pii_type, f.value) for f in result.findings]


def _match_spans(
    gold: list[Span],
    pred: list[Span],
) -> tuple[int, int, set[int], set[int]]:
    unmatched_gold = set(range(len(gold)))
    unmatched_pred = set(range(len(pred)))
    exact_tp = 0
    overlap_tp = 0

    for pi, predicted in enumerate(pred):
        candidates = [
            gi
            for gi in unmatched_gold
            if predicted.pii_type == gold[gi].pii_type
            and predicted.start == gold[gi].start
            and predicted.end == gold[gi].end
        ]
        if candidates:
            gi = candidates[0]
            unmatched_gold.remove(gi)
            unmatched_pred.remove(pi)
            exact_tp += 1

    for pi in list(unmatched_pred):
        predicted = pred[pi]
        candidates = [
            gi
            for gi in unmatched_gold
            if predicted.pii_type == gold[gi].pii_type
            and predicted.overlaps(gold[gi])
        ]
        if candidates:
            gi = candidates[0]
            unmatched_gold.remove(gi)
            unmatched_pred.remove(pi)
            overlap_tp += 1

    return exact_tp, overlap_tp, unmatched_gold, unmatched_pred


def _char_positions(spans: Iterable[Span]) -> set[int]:
    chars: set[int] = set()
    for span in spans:
        chars.update(range(span.start, span.end))
    return chars


def _ratio(
    numerator: float,
    denominator: float,
    *,
    empty: float | None = 0.0,
) -> float | None:
    return numerator / denominator if denominator else empty


def _span_payload(span: Span) -> dict:
    return {
        "start": span.start,
        "end": span.end,
        "pii_type": span.pii_type,
        "value": span.value,
    }


def _quality_from_counts(
    *,
    tp: int,
    fp: int,
    fn: int,
) -> dict[str, float | None]:
    recall = _ratio(tp, tp + fn, empty=1.0)
    precision = _ratio(tp, tp + fp, empty=None)
    if precision is None or recall is None:
        f1 = None
    elif precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return {
        "pii_recall": recall,
        "precision": precision,
        "span_f1": f1,
    }


def score_case(case: Case, result: InferenceResult) -> dict:
    gold = list(case.gold)
    pred = _predicted_spans(result) if result.valid else []

    exact_tp, overlap_tp, unmatched_gold, unmatched_pred = _match_spans(gold, pred)
    tp = exact_tp + overlap_tp
    # Unresolved model values are explicit false-positive evidence instead of vanishing.
    fp = len(unmatched_pred) + (result.unresolved_item_count if result.valid else 0)
    fn = len(gold) - tp

    gold_chars = _char_positions(gold)
    pred_chars = _char_positions(pred)
    leaked_chars = len(gold_chars - pred_chars)
    overredacted_chars = len(pred_chars - gold_chars)
    non_pii_chars = max(1, len(case.text) - len(gold_chars))

    quality = _quality_from_counts(tp=tp, fp=fp, fn=fn) if result.valid else {
        "pii_recall": None,
        "precision": None,
        "span_f1": None,
    }
    leakage_rate = (
        _ratio(leaked_chars, len(gold_chars))
        if result.valid
        else None
    )
    over_redaction_rate = (
        _ratio(overredacted_chars, non_pii_chars)
        if result.valid
        else None
    )

    by_type: dict[str, dict] = {}
    pii_types = sorted({span.pii_type for span in gold} | {span.pii_type for span in pred})
    for pii_type in pii_types:
        type_gold = [span for span in gold if span.pii_type == pii_type]
        type_pred = [span for span in pred if span.pii_type == pii_type]
        type_exact, type_overlap, type_unmatched_gold, type_unmatched_pred = _match_spans(
            type_gold,
            type_pred,
        )
        type_tp = type_exact + type_overlap
        type_fn = len(type_unmatched_gold)
        type_fp = len(type_unmatched_pred)
        type_gold_chars = _char_positions(type_gold)
        type_pred_chars = _char_positions(type_pred)
        type_leaked_chars = len(type_gold_chars - type_pred_chars)
        type_quality = (
            _quality_from_counts(tp=type_tp, fp=type_fp, fn=type_fn)
            if result.valid
            else {"pii_recall": None, "precision": None, "span_f1": None}
        )
        by_type[pii_type] = {
            "gold_count": len(type_gold),
            "predicted_count": len(type_pred) if result.valid else 0,
            "tp": type_tp if result.valid else 0,
            "exact_tp": type_exact if result.valid else 0,
            "overlap_tp": type_overlap if result.valid else 0,
            "fp": type_fp if result.valid else 0,
            "fn": type_fn if result.valid else 0,
            "gold_chars": len(type_gold_chars),
            "leaked_chars": type_leaked_chars if result.valid else 0,
            "pii_recall": type_quality["pii_recall"],
            "precision": type_quality["precision"],
            "span_f1": type_quality["span_f1"],
            "leakage_rate": (
                _ratio(type_leaked_chars, len(type_gold_chars))
                if result.valid
                else None
            ),
        }

    system_tp = tp if result.valid else 0
    system_fp = fp if result.valid else 0
    system_fn = fn if result.valid else len(gold)
    system_leaked_chars = leaked_chars if result.valid else len(gold_chars)

    return {
        "case_id": case.case_id,
        "profile": case.profile,
        "tags": list(case.tags),
        "model": result.model,
        "valid": result.valid,
        "quality_available": result.valid,
        "inference_status": result.status,
        "error_type": result.error_type,
        "http_status": result.http_status,
        "finish_reason": result.finish_reason,
        "latency_ms": result.latency_ms,
        "gold_count": len(gold),
        "predicted_count": (len(pred) + result.unresolved_item_count) if result.valid else 0,
        "raw_item_count": result.raw_item_count,
        "resolved_item_count": result.resolved_item_count,
        "unresolved_item_count": result.unresolved_item_count,
        "tp": tp if result.valid else 0,
        "exact_tp": exact_tp if result.valid else 0,
        "overlap_tp": overlap_tp if result.valid else 0,
        "fp": fp if result.valid else 0,
        "fn": fn if result.valid else 0,
        "pii_recall": quality["pii_recall"],
        "precision": quality["precision"],
        "span_f1": quality["span_f1"],
        "exact_match_recall": (
            _ratio(exact_tp, len(gold), empty=1.0)
            if result.valid
            else None
        ),
        "zero_leak": result.valid and fn == 0 and leaked_chars == 0,
        "leaked_chars": leaked_chars if result.valid else 0,
        "gold_chars": len(gold_chars),
        "leakage_rate": leakage_rate,
        "overredacted_chars": overredacted_chars if result.valid else 0,
        "non_pii_chars": non_pii_chars,
        "over_redaction_rate": over_redaction_rate,
        "system_tp": system_tp,
        "system_fp": system_fp,
        "system_fn": system_fn,
        "system_leaked_chars": system_leaked_chars,
        "system_pii_recall": _quality_from_counts(
            tp=system_tp,
            fp=system_fp,
            fn=system_fn,
        )["pii_recall"],
        "system_leakage_rate": _ratio(system_leaked_chars, len(gold_chars)),
        "by_type": by_type,
        "false_negatives": (
            [_span_payload(gold[index]) for index in sorted(unmatched_gold)]
            if result.valid
            else []
        ),
        "false_positives": (
            [_span_payload(pred[index]) for index in sorted(unmatched_pred)]
            if result.valid
            else []
        ),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "error": result.error,
    }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    low = int(idx)
    high = min(low + 1, len(ordered) - 1)
    frac = idx - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def aggregate(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    valid_rows = [row for row in rows if row["valid"]]

    tp = sum(row["tp"] for row in valid_rows)
    fp = sum(row["fp"] for row in valid_rows)
    fn = sum(row["fn"] for row in valid_rows)
    exact_tp = sum(row["exact_tp"] for row in valid_rows)
    quality_gold_count = sum(row["gold_count"] for row in valid_rows)
    predicted_count = sum(row["predicted_count"] for row in valid_rows)
    quality_gold_chars = sum(row["gold_chars"] for row in valid_rows)
    leaked_chars = sum(row["leaked_chars"] for row in valid_rows)
    over_chars = sum(row["overredacted_chars"] for row in valid_rows)
    non_pii_chars = sum(row["non_pii_chars"] for row in valid_rows)
    latencies = [row["latency_ms"] for row in valid_rows]

    quality = (
        _quality_from_counts(tp=tp, fp=fp, fn=fn)
        if valid_rows
        else {"pii_recall": None, "precision": None, "span_f1": None}
    )

    system_tp = sum(row["system_tp"] for row in rows)
    system_fp = sum(row["system_fp"] for row in rows)
    system_fn = sum(row["system_fn"] for row in rows)
    system_gold_chars = sum(row["gold_chars"] for row in rows)
    system_leaked_chars = sum(row["system_leaked_chars"] for row in rows)
    system_quality = _quality_from_counts(
        tp=system_tp,
        fp=system_fp,
        fn=system_fn,
    )

    raw_items = sum(row.get("raw_item_count", 0) for row in valid_rows)
    resolved_items = sum(row.get("resolved_item_count", 0) for row in valid_rows)
    unresolved_items = sum(row.get("unresolved_item_count", 0) for row in valid_rows)
    statuses = Counter(row.get("inference_status") or "unknown" for row in rows)

    return {
        "status": "ok" if valid_rows else "no_valid_inference",
        "quality_available": bool(valid_rows),
        "cases": len(rows),
        "evaluated_cases": len(valid_rows),
        "inference_failures": len(rows) - len(valid_rows),
        "inference_success_rate": len(valid_rows) / len(rows) if rows else 0.0,
        "evaluated_case_coverage": len(valid_rows) / len(rows) if rows else 0.0,
        "valid_output_rate": len(valid_rows) / len(rows) if rows else 0.0,
        "contract_valid_rate": len(valid_rows) / len(rows) if rows else 0.0,
        "truncation_rate": (
            statuses.get("truncated_output", 0) / len(rows)
            if rows
            else 0.0
        ),
        "inference_statuses": dict(statuses),
        "gold_count": sum(row["gold_count"] for row in rows),
        "quality_gold_count": quality_gold_count,
        "predicted_count": predicted_count,
        "raw_item_count": raw_items,
        "resolved_item_count": resolved_items,
        "unresolved_item_count": unresolved_items,
        "span_resolution_rate": _ratio(resolved_items, raw_items, empty=1.0),
        "tp": tp,
        "exact_tp": exact_tp,
        "fp": fp,
        "fn": fn,
        "pii_recall": quality["pii_recall"],
        "precision": quality["precision"],
        "span_f1": quality["span_f1"],
        "exact_match_recall": (
            _ratio(exact_tp, quality_gold_count, empty=1.0)
            if valid_rows
            else None
        ),
        "leakage_rate": (
            _ratio(leaked_chars, quality_gold_chars)
            if valid_rows
            else None
        ),
        "zero_leak_document_rate": (
            sum(bool(row["zero_leak"]) for row in valid_rows) / len(valid_rows)
            if valid_rows
            else None
        ),
        "over_redaction_rate": (
            _ratio(over_chars, non_pii_chars)
            if valid_rows
            else None
        ),
        "leaked_chars": leaked_chars,
        "gold_chars": quality_gold_chars,
        "overredacted_chars": over_chars,
        "non_pii_chars": non_pii_chars,
        "latency_p50_ms": median(latencies) if latencies else None,
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
        "failures": len(rows) - len(valid_rows),
        "system_tp": system_tp,
        "system_fp": system_fp,
        "system_fn": system_fn,
        "system_pii_recall": system_quality["pii_recall"],
        "system_leakage_rate": _ratio(
            system_leaked_chars,
            system_gold_chars,
        ),
        "system_zero_leak_document_rate": (
            sum(
                bool(row["valid"])
                and row["system_fn"] == 0
                and row["system_leaked_chars"] == 0
                for row in rows
            )
            / len(rows)
            if rows
            else 0.0
        ),
        "errors": dict(
            Counter(
                row.get("error_type") or row.get("error")
                for row in rows
                if row.get("error_type") or row.get("error")
            )
        ),
    }


def _average(values: Iterable[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    return sum(filtered) / len(filtered) if filtered else None


def _aggregate_type_rows(rows: list[dict]) -> dict[str, dict]:
    valid_rows = [row for row in rows if row["valid"]]
    counters: dict[str, Counter] = defaultdict(Counter)
    for row in valid_rows:
        for pii_type, summary in row.get("by_type", {}).items():
            counters[pii_type].update(
                {
                    "gold_count": summary["gold_count"],
                    "predicted_count": summary["predicted_count"],
                    "tp": summary["tp"],
                    "exact_tp": summary["exact_tp"],
                    "overlap_tp": summary["overlap_tp"],
                    "fp": summary["fp"],
                    "fn": summary["fn"],
                    "gold_chars": summary["gold_chars"],
                    "leaked_chars": summary["leaked_chars"],
                }
            )

    result: dict[str, dict] = {}
    for pii_type, counts in sorted(counters.items()):
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        quality = _quality_from_counts(tp=tp, fp=fp, fn=fn)
        result[pii_type] = {
            **dict(counts),
            "pii_recall": quality["pii_recall"],
            "precision": quality["precision"],
            "span_f1": quality["span_f1"],
            "exact_match_recall": _ratio(
                counts["exact_tp"],
                counts["gold_count"],
                empty=1.0,
            ),
            "leakage_rate": _ratio(
                counts["leaked_chars"],
                counts["gold_chars"],
            ),
        }
    return result


def _document_summary(case_rows: list[dict]) -> dict:
    summary = aggregate(case_rows)
    valid_case_rows = [row for row in case_rows if row["valid"]]
    representative = (
        max(
            valid_case_rows,
            key=lambda row: (
                row.get("leakage_rate") or 0.0,
                row.get("fn", 0),
                row.get("fp", 0),
                row.get("over_redaction_rate") or 0.0,
            ),
        )
        if valid_case_rows
        else case_rows[0]
    )
    summary.update(
        {
            "profile": case_rows[0]["profile"],
            "tags": case_rows[0].get("tags", []),
            "gold_count_per_document": case_rows[0]["gold_count"],
            "false_negatives": representative.get("false_negatives", []),
            "false_positives": representative.get("false_positives", []),
            "representative_error": representative.get("error"),
            "representative_error_type": representative.get("error_type"),
            "representative_status": representative.get("inference_status"),
            "unresolved_item_count": sum(
                row.get("unresolved_item_count", 0)
                for row in valid_case_rows
            ),
        }
    )
    return summary


def _macro_summary(by_document: dict[str, dict]) -> dict:
    documents = list(by_document.values())
    metric_keys = (
        "pii_recall",
        "precision",
        "span_f1",
        "exact_match_recall",
        "leakage_rate",
        "over_redaction_rate",
        "inference_success_rate",
        "zero_leak_document_rate",
        "system_pii_recall",
        "system_leakage_rate",
    )
    summary = {
        key: _average(document.get(key) for document in documents)
        for key in metric_keys
    }
    summary["documents"] = len(documents)
    summary["evaluated_documents"] = sum(
        bool(document.get("quality_available"))
        for document in documents
    )
    return summary


def _dataset_balance(rows: list[dict]) -> dict:
    first_by_case: dict[str, dict] = {}
    for row in rows:
        first_by_case.setdefault(row["case_id"], row)

    per_document = {
        case_id: row["gold_count"]
        for case_id, row in sorted(first_by_case.items())
    }
    total_gold = sum(per_document.values())
    if per_document:
        largest_document = max(per_document, key=per_document.get)
        largest_count = per_document[largest_document]
    else:
        largest_document = None
        largest_count = 0

    by_type: Counter = Counter()
    for row in first_by_case.values():
        for pii_type, summary in row.get("by_type", {}).items():
            by_type[pii_type] += summary["gold_count"]

    return {
        "documents": len(per_document),
        "gold_spans": total_gold,
        "gold_spans_by_document": per_document,
        "gold_spans_by_type": dict(sorted(by_type.items())),
        "largest_document": largest_document,
        "largest_document_gold_spans": largest_count,
        "largest_document_share": _ratio(largest_count, total_gold),
    }


def aggregate_detailed(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    micro = aggregate(rows)

    grouped_documents: dict[str, list[dict]] = defaultdict(list)
    grouped_profiles: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped_documents[row["case_id"]].append(row)
        grouped_profiles[row["profile"]].append(row)

    by_document = {
        case_id: _document_summary(case_rows)
        for case_id, case_rows in sorted(grouped_documents.items())
    }
    by_profile = {
        profile: aggregate(profile_rows)
        for profile, profile_rows in sorted(grouped_profiles.items())
    }
    by_type = _aggregate_type_rows(rows)
    macro = _macro_summary(by_document)

    failures = []
    for case_id, summary in by_document.items():
        if (
            summary["inference_failures"]
            or summary["fn"]
            or summary["fp"]
            or summary["leaked_chars"]
            or summary["overredacted_chars"]
            or summary.get("unresolved_item_count")
        ):
            failures.append(
                {
                    "case_id": case_id,
                    "profile": summary["profile"],
                    "quality_available": summary["quality_available"],
                    "inference_status": summary["representative_status"],
                    "error_type": summary["representative_error_type"],
                    "pii_recall": summary["pii_recall"],
                    "precision": summary["precision"],
                    "leakage_rate": summary["leakage_rate"],
                    "system_pii_recall": summary["system_pii_recall"],
                    "system_leakage_rate": summary["system_leakage_rate"],
                    "over_redaction_rate": summary["over_redaction_rate"],
                    "fn": summary["fn"],
                    "fp": summary["fp"],
                    "system_fn": summary["system_fn"],
                    "inference_failures": summary["inference_failures"],
                    "unresolved_item_count": summary.get("unresolved_item_count", 0),
                    "false_negatives": summary["false_negatives"],
                    "false_positives": summary["false_positives"],
                    "error": summary["representative_error"],
                }
            )
    failures.sort(
        key=lambda item: (
            item["inference_failures"],
            item["system_leakage_rate"] or 0.0,
            item["system_fn"],
            item["fp"],
        ),
        reverse=True,
    )

    return {
        **micro,
        "evaluation_schema": EVALUATION_SCHEMA,
        "micro": micro,
        "macro": macro,
        "by_type": by_type,
        "by_profile": by_profile,
        "by_document": by_document,
        "dataset_balance": _dataset_balance(rows),
        "failure_analysis": failures,
    }
