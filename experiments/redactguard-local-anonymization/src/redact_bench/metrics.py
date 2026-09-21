from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Iterable

from redact_bench.models import Case, Finding, InferenceResult, Span


def _predicted_spans(result: InferenceResult) -> list[Span]:
    return [Span(f.start, f.end, f.pii_type, f.value) for f in result.findings]


def score_case(case: Case, result: InferenceResult) -> dict:
    gold = list(case.gold)
    pred = _predicted_spans(result)

    unmatched_gold = set(range(len(gold)))
    unmatched_pred = set(range(len(pred)))
    exact_tp = 0
    overlap_tp = 0

    for pi, p in enumerate(pred):
        candidates = [
            gi for gi in unmatched_gold
            if p.pii_type == gold[gi].pii_type and p.start == gold[gi].start and p.end == gold[gi].end
        ]
        if candidates:
            gi = candidates[0]
            unmatched_gold.remove(gi)
            unmatched_pred.remove(pi)
            exact_tp += 1

    remaining_gold = set(unmatched_gold)
    remaining_pred = set(unmatched_pred)
    for pi in list(remaining_pred):
        p = pred[pi]
        candidates = [
            gi for gi in remaining_gold
            if p.pii_type == gold[gi].pii_type and p.overlaps(gold[gi])
        ]
        if candidates:
            gi = candidates[0]
            remaining_gold.remove(gi)
            remaining_pred.remove(pi)
            overlap_tp += 1

    tp = exact_tp + overlap_tp
    fn = len(gold) - tp
    fp = len(pred) - tp

    gold_chars = set()
    pred_chars = set()
    for span in gold:
        gold_chars.update(range(span.start, span.end))
    for span in pred:
        pred_chars.update(range(span.start, span.end))

    leaked_chars = len(gold_chars - pred_chars)
    overredacted_chars = len(pred_chars - gold_chars)
    non_pii_chars = max(1, len(case.text) - len(gold_chars))

    return {
        "case_id": case.case_id,
        "profile": case.profile,
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
        "zero_leak": result.valid and fn == 0 and leaked_chars == 0,
        "leaked_chars": leaked_chars,
        "gold_chars": len(gold_chars),
        "overredacted_chars": overredacted_chars,
        "non_pii_chars": non_pii_chars,
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
    gold_chars = sum(row["gold_chars"] for row in rows)
    leaked_chars = sum(row["leaked_chars"] for row in rows)
    over_chars = sum(row["overredacted_chars"] for row in rows)
    non_pii_chars = sum(row["non_pii_chars"] for row in rows)
    latencies = [row["latency_ms"] for row in valid_rows]

    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "cases": len(rows),
        "valid_output_rate": len(valid_rows) / len(rows) if rows else 0.0,
        "pii_recall": recall,
        "precision": precision,
        "span_f1": f1,
        "leakage_rate": leaked_chars / gold_chars if gold_chars else 0.0,
        "zero_leak_document_rate": (
            sum(bool(row["zero_leak"]) for row in rows) / len(rows)
            if rows else 0.0
        ),
        "over_redaction_rate": over_chars / non_pii_chars if non_pii_chars else 0.0,
        "latency_p50_ms": median(latencies) if latencies else None,
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
        "failures": len(rows) - len(valid_rows),
        "errors": dict(Counter(row["error"] for row in rows if row["error"])),
    }
