"""Privacy-preserving, reproducible audit of a completed managed RedactGuard suite.

Consumes already persisted per-case metrics, not the documents/model response text.
Micro recall is dominated by cases with many entities; also report per-document and
per-semantic-family macro recalls so large XLSX files cannot silently hide errors.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _p(value: float | None) -> str:
    return f"{100 * value:.1f}%" if value is not None else "n/a"


def build_suite_audit(suite_dir: Path) -> dict:
    suite_dir = Path(suite_dir).expanduser()
    quality = suite_dir / "quality"
    rows_path = quality / "rows.json"
    if not rows_path.is_file():
        raise ValueError(f"Missing aggregated quality rows; suite may not be complete: {rows_path}")
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Empty or invalid quality rows: {rows_path}")

    status_path = suite_dir / "suite.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[str(row["model"])].append(row)

    unique_cases = {str(r["case_id"]): r for r in rows}
    gold_sum = sum(int(r["gold_count"]) for r in unique_cases.values())
    largest = max(unique_cases.values(), key=lambda r: int(r["gold_count"]))
    unreviewed = [case_id for case_id, row in unique_cases.items()
                  if row.get("human_reviewed") is not True]
    report: dict = {
        "suite_id": status.get("suite_id", suite_dir.name),
        "status": status.get("status", "unknown"),
        "data_status": {
            "documents": len(unique_cases),
            "total_gold_entities": gold_sum,
            "largest_document": str(largest["case_id"]),
            "largest_document_gold_share": (
                int(largest["gold_count"]) / gold_sum if gold_sum else None
            ),
            "human_reviewed": len(unique_cases) - len(unreviewed),
            "unreviewed_case_ids": sorted(unreviewed),
            "semantic_families": len({
                str(r.get("content_family_id") or r["case_id"])
                for r in unique_cases.values()
            }),
        },
        "inference_cache_max_entries": status.get("inference_cache_max_entries"),
        "models": {},
    }

    for model, group in sorted(by_model.items()):
        tp = sum(int(r.get("system_tp") or 0) for r in group)
        gold = sum(int(r.get("gold_count") or 0) for r in group)
        by_family: dict[str, list[float]] = defaultdict(list)
        by_extension: dict[str, list[float]] = defaultdict(list)
        failures: list[dict] = []
        for row in group:
            case_id = str(row["case_id"])
            recall = float(row.get("system_pii_recall") or 0)
            by_family[str(row.get("content_family_id") or case_id)].append(recall)
            extension = Path(case_id).suffix.lower() or "(none)"
            by_extension[extension].append(recall)
            if not row.get("valid", False):
                error = str(row.get("error") or "")
                # Output error classes/segment index only. Do not export source
                # PII, raw completions, or arbitrary exception strings.
                import re

                match = re.search(r"segment (\d+)/(\d+)", error)
                failures.append({
                    "case_id": case_id,
                    "error_type": str(row.get("error_type") or "unknown"),
                    "http_status": row.get("http_status"),
                    "failed_segment": (
                        {"index": int(match.group(1)), "total": int(match.group(2))}
                        if match else None
                    ),
                    "invalid_json": "invalid json" in error.lower(),
                })
        family_macro = [_mean(v) for v in by_family.values()]
        log_path = suite_dir / "logs" / f"{model.replace('/', '_')}.log"
        cache_hits = (
            log_path.read_text(encoding="utf-8", errors="replace").count("Inference cache hit")
            if log_path.exists() else None
        )
        report["models"][model] = {
            "valid_documents": sum(bool(r.get("valid")) for r in group),
            "total_documents": len(group),
            "system_micro_recall": tp / gold if gold else None,
            "system_macro_document_recall": _mean([
                float(r.get("system_pii_recall") or 0) for r in group
            ]),
            "system_macro_semantic_family_recall": _mean([
                v for v in family_macro if v is not None
            ]),
            "system_macro_by_extension": {
                ext: _mean(values) for ext, values in sorted(by_extension.items())
            },
            "zero_leak_documents": sum(
                bool(r.get("valid")) and bool(r.get("zero_leak"))
                for r in group
            ),
            "inference_cache_hits_in_korgis_log": cache_hits,
            "failures": failures,
        }
    return report


def write_suite_audit(suite_dir: Path) -> tuple[Path, Path]:
    root = Path(suite_dir).expanduser()
    data = build_suite_audit(root)
    json_path = root / "audit.json"
    md_path = root / "audit.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    d = data["data_status"]
    lines = [
        "# RedactGuard managed suite — quality/methodology audit", "",
        f"Suite: `{data['suite_id']}` | status: `{data['status']}`", "",
        f"Gold entities: {d['total_gold_entities']} in {d['documents']} document variants "
        f"and {d['semantic_families']} semantic families.",
        f"Largest document: `{d['largest_document']}` "
        f"({_p(d['largest_document_gold_share'])} of all gold entities).",
        f"Human-reviewed: {d['human_reviewed']}/{d['documents']} "
        "(unreviewed labels must not be treated as adjudicated ground truth).",
        "",
        "## Quality by model", "",
        "| Model | Valid | Micro recall (all) | Macro doc recall | Macro family recall | Zero-leak | HTTP cache hits |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, m in data["models"].items():
        hits = m["inference_cache_hits_in_korgis_log"]
        lines.append(
            f"| `{model}` | {m['valid_documents']}/{m['total_documents']} | "
            f"{_p(m['system_micro_recall'])} | "
            f"{_p(m['system_macro_document_recall'])} | "
            f"{_p(m['system_macro_semantic_family_recall'])} | "
            f"{m['zero_leak_documents']}/{m['total_documents']} | "
            f"{hits if hits is not None else 'n/a'} |"
        )
    lines += [
        "", "Micro recall weights individual PII entities. Macro doc recall equally weights "
        "document variants; macro family recall equally weights semantic content families.",
        "Failed/invalid documents count as zero recall in all three.",
        "",
        "## Backend failures (without PII values)", "",
    ]
    for model, m in data["models"].items():
        lines.append(f"### {model}")
        if not m["failures"]:
            lines.append("No invalid documents.")
        for f in m["failures"]:
            seg = f["failed_segment"]
            detail = f"; segment {seg['index']}/{seg['total']}" if seg else ""
            lines.append(f"- `{f['case_id']}` — {f['error_type']} "
                         f"(HTTP {f['http_status']}, invalid JSON={f['invalid_json']}{detail})")
        lines.append("")
    if data["inference_cache_max_entries"] is None:
        lines.append("**Warning:** legacy suite does not prove response caching was disabled; "
                     "do not rank latency without inspecting the server logs.")
    elif data["inference_cache_max_entries"] != 0:
        lines.append("**Warning:** response caching was enabled; latency may be invalid.")
    else:
        lines.append("Cache-off was requested in the suite configuration; confirm zero "
                     "cache-hit events in per-model Korgis logs.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
