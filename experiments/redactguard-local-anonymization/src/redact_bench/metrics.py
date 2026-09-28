from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Iterable

from redact_bench.models import Case, InferenceResult, Span


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


def _ratio(numerator: float, denominator: float, *, empty: float = 0.0) -> float:
    return numerator / denominator if denominator else empty


def _span_payload(span: Span) -> dict:
    return {
        "start": span.start,
        "end": span.end,
        "pii_type": span.pii_type,
        "value": span.value,
    }


def _quality_from_counts(*, tp: int, fp: int, fn: int) -> dict[str, float]:
    recall = _ratio(tp, tp + fn, empty=1.0)
    precision = _ratio(tp, tp + fp, empty=1.0)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "pii_recall": recall,
        "precision": precision,
        "span_f1": f1,
    }


def score_case(case: Case, result: InferenceResult) -> dict:
    gold = list(case.gold)
    pred = _predicted_spans(result)

    exact_tp, overlap_tp, unmatched_gold, unmatched_pred = _match_spans(gold, pred)
    tp = exact_tp + overlap_tp
    fn = len(gold) - tp
    fp = len(pred) - tp

    gold_chars = _char_positions(gold)
    pred_chars = _char_positions(pred)
    leaked_chars = len(gold_chars - pred_chars)
    overredacted_chars = len(pred_chars - gold_chars)
    non_pii_chars = max(1, len(case.text) - len(gold_chars))

    quality = _quality_from_counts(tp=tp, fp=fp, fn=fn)
    leakage_rate = _ratio(leaked_chars, len(gold_chars))
    over_redaction_rate = _ratio(overredacted_chars, non_pii_chars)

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
        type_quality = _quality_from_counts(tp=type_tp, fp=type_fp, fn=type_fn)
        by_type[pii_type] = {
            "gold_count": len(type_gold),
            "predicted_count": len(type_pred),
            "tp": type_tp,
            "exact_tp": type_exact,
            "overlap_tp": type_overlap,
            "fp": type_fp,
            "fn": type_fn,
            "gold_chars": len(type_gold_chars),
            "leaked_chars": type_leaked_chars,
            "pii_recall": type_quality["pii_recall"],
            "precision": type_quality["precision"],
            "span_f1": type_quality["span_f1"],
            "leakage_rate": _ratio(type_leaked_chars, len(type_gold_chars)),
        }

    return {
        "case_id": case.case_id,
        "profile": case.profile,
        "tags": list(case.tags),
        "model": result.model,
        "valid": result.valid,
        "latency_ms": result.latency_ms,
        "gold_count": len(gold),
        "predicted_count": len(pred),
        "tp": tp,
        "exact_tp": exact_tp,
        "overlap_tp": overlap_tp,
        "fp": fp,
        "fn": fn,
        "pii_recall": quality["pii_recall"],
        "precision": quality["precision"],
        "span_f1": quality["span_f1"],
        "exact_match_recall": _ratio(exact_tp, len(gold), empty=1.0),
        "zero_leak": result.valid and fn == 0 and leaked_chars == 0,
        "leaked_chars": leaked_chars,
        "gold_chars": len(gold_chars),
        "leakage_rate": leakage_rate,
        "overredacted_chars": overredacted_chars,
        "non_pii_chars": non_pii_chars,
        "over_redaction_rate": over_redaction_rate,
        "by_type": by_type,
        "false_negatives": [_span_payload(gold[index]) for index in sorted(unmatched_gold)],
        "false_positives": [_span_payload(pred[index]) for index in sorted(unmatched_pred)],
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
    tp = sum(row["tp"] for row in rows)
    fp = sum(row["fp"] for row in rows)
    fn = sum(row["fn"] for row in rows)
    exact_tp = sum(row["exact_tp"] for row in rows)
    gold_count = sum(row["gold_count"] for row in rows)
    predicted_count = sum(row["predicted_count"] for row in rows)
    gold_chars = sum(row["gold_chars"] for row in rows)
    leaked_chars = sum(row["leaked_chars"] for row in rows)
    over_chars = sum(row["overredacted_chars"] for row in rows)
    non_pii_chars = sum(row["non_pii_chars"] for row in rows)
    latencies = [row["latency_ms"] for row in valid_rows]

    quality = _quality_from_counts(tp=tp, fp=fp, fn=fn)

    return {
        "cases": len(rows),
        "valid_output_rate": len(valid_rows) / len(rows) if rows else 0.0,
        "gold_count": gold_count,
        "predicted_count": predicted_count,
        "tp": tp,
        "exact_tp": exact_tp,
        "fp": fp,
        "fn": fn,
        "pii_recall": quality["pii_recall"],
        "precision": quality["precision"],
        "span_f1": quality["span_f1"],
        "exact_match_recall": _ratio(exact_tp, gold_count, empty=1.0),
        "leakage_rate": _ratio(leaked_chars, gold_chars),
        "zero_leak_document_rate": (
            sum(bool(row["zero_leak"]) for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "over_redaction_rate": _ratio(over_chars, non_pii_chars),
        "leaked_chars": leaked_chars,
        "gold_chars": gold_chars,
        "overredacted_chars": over_chars,
        "non_pii_chars": non_pii_chars,
        "latency_p50_ms": median(latencies) if latencies else None,
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
        "failures": len(rows) - len(valid_rows),
        "errors": dict(Counter(row["error"] for row in rows if row["error"])),
    }


def _average(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _aggregate_type_rows(rows: list[dict]) -> dict[str, dict]:
    counters: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
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
    worst = max(
        case_rows,
        key=lambda row: (
            row["leakage_rate"],
            row["fn"],
            row["fp"],
            row["over_redaction_rate"],
        ),
    )
    summary.update(
        {
            "profile": case_rows[0]["profile"],
            "tags": case_rows[0].get("tags", []),
            "gold_count_per_document": case_rows[0]["gold_count"],
            "false_negatives": worst.get("false_negatives", []),
            "false_positives": worst.get("false_positives", []),
            "representative_error": worst.get("error"),
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
        "valid_output_rate",
        "zero_leak_document_rate",
    )
    summary = {
        key: _average(document[key] for document in documents)
        for key in metric_keys
    }
    summary["documents"] = len(documents)
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
            summary["fn"]
            or summary["fp"]
            or summary["failures"]
            or summary["leaked_chars"]
            or summary["overredacted_chars"]
        ):
            failures.append(
                {
                    "case_id": case_id,
                    "profile": summary["profile"],
                    "pii_recall": summary["pii_recall"],
                    "precision": summary["precision"],
                    "leakage_rate": summary["leakage_rate"],
                    "over_redaction_rate": summary["over_redaction_rate"],
                    "fn": summary["fn"],
                    "fp": summary["fp"],
                    "failures": summary["failures"],
                    "false_negatives": summary["false_negatives"],
                    "false_positives": summary["false_positives"],
                    "error": summary["representative_error"],
                }
            )
    failures.sort(
        key=lambda item: (
            item["leakage_rate"],
            item["fn"],
            item["fp"],
            item["over_redaction_rate"],
        ),
        reverse=True,
    )

    return {
        **micro,
        "evaluation_schema": "redactguard-evaluation-v2",
        "micro": micro,
        "macro": macro,
        "by_type": by_type,
        "by_profile": by_profile,
        "by_document": by_document,
        "dataset_balance": _dataset_balance(rows),
        "failure_analysis": failures,
    }
