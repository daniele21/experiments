"""Run native Decisio and its JSON comparator on identical routing cases, CPU only.

Run with the Decisio virtualenv's Python; no changes to that checkout are needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EVENT_PREFIX = "DECISIO_EVENT "


def emit_event(args, event, **fields):
    if args.events_json:
        print(EVENT_PREFIX + json.dumps({"event": event, **fields}), flush=True)
    elif event == "phase":
        print(fields["status"], flush=True)
    elif event == "case":
        print(
            f"{args.model.stem} {fields['method']} {fields['completed']}/{fields['total']} "
            f"correct={fields['correct']} {fields['latency_ms']:.0f}ms",
            flush=True,
        )


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def summarize(rows):
    labels = sorted({r["expected"] for r in rows})
    f1s = []
    for label in labels:
        tp = sum(r["expected"] == label and r["choice"] == label for r in rows)
        fp = sum(r["expected"] != label and r["choice"] == label for r in rows)
        fn = sum(r["expected"] == label and r["choice"] != label for r in rows)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0)
    return {
        "cases": len(rows),
        "correct": sum(r["correct"] for r in rows),
        "accuracy": statistics.mean(r["correct"] for r in rows),
        "macro_f1": statistics.mean(f1s),
        "valid_rate": statistics.mean(r["valid"] for r in rows),
        "latency_p50_ms": percentile([r["latency_ms"] for r in rows], 0.5),
        "latency_p95_ms": percentile([r["latency_ms"] for r in rows], 0.95),
        "generated_tokens": sum(r["result"].get("generated_tokens", 0) for r in rows),
        "cache_hits": sum(r["runtime"].get("repeated_state_cache_hits", 0) for r in rows),
        "errors": [
            {
                "case_id": r["case_id"],
                "expected": r["expected"],
                "choice": r["choice"],
                "error": r.get("error"),
            }
            for r in rows
            if not r["correct"]
        ],
    }


def load_resume_rows(path, *, methods, case_ids):
    if not path.exists():
        return []
    rows = []
    seen = set()
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path} at line {line_number}: {exc}") from exc
        key = (row.get("method"), row.get("case_id"))
        if key[0] not in methods or key[1] not in case_ids:
            raise ValueError(f"unexpected saved result at line {line_number}: {key}")
        if key in seen:
            raise ValueError(f"duplicate saved result at line {line_number}: {key}")
        seen.add(key)
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisio-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--dataset", choices=["smoke", "banking77"], default="smoke")
    parser.add_argument("--cases", type=int, default=None)
    parser.add_argument("--methods", default="direct,json")
    parser.add_argument("--device", choices=["cpu", "metal"], default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events-json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume a compatible partial run from --output",
    )
    args = parser.parse_args()
    if args.cases is not None and args.cases < 1:
        parser.error("--cases must be positive")
    methods = args.methods.split(",")
    if not set(methods) <= {"direct", "fresh", "semantic", "json"}:
        parser.error("methods: direct,fresh,semantic,json")
    if args.dataset == "banking77" and set(methods) & {"direct", "fresh"}:
        parser.error(
            "Native letter scorer supports 26 candidates; BANKING77 requires semantic,json"
        )
    sys.path.insert(0, str(args.decisio_root.resolve() / "src"))
    from decisio.backends.llama_cpp import LlamaCppBackend, LlamaCppBackendConfig
    from decisio.baselines.generation import GeneratedJsonScorer
    from decisio.schema import Candidate, ChoiceRequest
    from decisio.scorers.letters import LetterTokenScorer
    from decisio.scorers.semantic import SemanticBinaryScorer

    from jev_bench.datasets import routing_cases, routing_questions

    emit_event(args, "phase", status="Preparing dataset...")
    if args.dataset == "smoke":
        cases, question = routing_cases(), routing_questions()[0]
        random.Random(42).shuffle(cases)
        if args.cases:
            cases = cases[: args.cases]
    else:
        from jev_bench.benchmark_data import balanced_banking77_cases, banking77_question

        cache = ROOT / "data/cache"
        cases = balanced_banking77_cases(cache, max_cases=args.cases, seed=42)
        question = banking77_question(cache)
    candidates = tuple(Candidate(k, v) for k, v in question.criteria.items())
    fixture = {"question": asdict(question), "cases": [asdict(c) for c in cases]}
    fixture_text = json.dumps(fixture, sort_keys=True, indent=2)
    fixture_sha256 = hashlib.sha256(fixture_text.encode()).hexdigest()
    if args.output.exists() and not args.resume:
        parser.error(
            f"output directory already exists: {args.output}; use --resume for a compatible "
            "partial run or choose a new --output"
        )
    if args.resume:
        if not args.output.is_dir():
            parser.error(f"cannot resume because output directory does not exist: {args.output}")
        fixture_path = args.output / "fixture.json"
        manifest_path = args.output / "manifest.json"
        if not fixture_path.is_file() or not manifest_path.is_file():
            parser.error("cannot resume: output must contain fixture.json and manifest.json")
        saved_fixture = fixture_path.read_text()
        if hashlib.sha256(saved_fixture.encode()).hexdigest() != fixture_sha256:
            parser.error("cannot resume: fixture does not match the requested dataset/cases")
        saved_manifest = json.loads(manifest_path.read_text())
        saved_model = Path(saved_manifest.get("config", {}).get("model", "")).expanduser()
        if saved_model.resolve() != args.model.expanduser().resolve():
            parser.error("cannot resume: model path differs from the saved run")
        if saved_manifest.get("methods") != methods:
            parser.error("cannot resume: --methods differs from the saved run")
        if saved_manifest.get("dataset") != args.dataset:
            parser.error("cannot resume: --dataset differs from the saved run")
        saved_threads = saved_manifest.get("config", {}).get("n_threads")
        if saved_threads != args.threads:
            parser.error("cannot resume: --threads differs from the saved run")
        saved_device = saved_manifest.get("config", {}).get("device", "cpu")
        if saved_device != args.device:
            parser.error("cannot resume: --device differs from the saved run")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "fixture.json").write_text(fixture_text)
    config = LlamaCppBackendConfig(
        model=args.model,
        device=args.device,
        n_threads=args.threads,
        n_threads_batch=args.threads,
    )
    emit_event(args, "phase", status="Loading GGUF and verifying artifact hash...")
    backend = LlamaCppBackend(config)
    try:
        # Force lazy model initialization outside measured requests.
        backend.tokenizer.encode("warmup")
        if args.resume:
            manifest = json.loads((args.output / "manifest.json").read_text())
            if manifest.get("model", {}).get("artifact_sha256") != backend.identity.get(
                "artifact_sha256"
            ):
                parser.error("cannot resume: model artifact hash differs from the saved run")
            manifest.setdefault("resumed_at", []).append(datetime.now(UTC).isoformat())
        else:
            manifest = {
                "timestamp": datetime.now(UTC).isoformat(),
                "decisio_sha": subprocess.check_output(
                    ["git", "-C", str(args.decisio_root), "rev-parse", "HEAD"], text=True
                ).strip(),
                "decisio_status": subprocess.check_output(
                    ["git", "-C", str(args.decisio_root), "status", "--porcelain"], text=True
                ),
                "model": backend.identity,
                "platform": platform.platform(),
                "config": {**asdict(config), "model": str(args.model)},
                "dataset": args.dataset,
                "fixture_sha256": fixture_sha256,
                "methods": methods,
                "seed": 42,
                "warmup_requests_per_method": 1,
                "probability_note": "Native scores are uncalibrated conditional preferences.",
            }
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
        scorers = {
            "direct": LetterTokenScorer(backend, reuse_prefix=True),
            "fresh": LetterTokenScorer(backend, reuse_prefix=True, shared_prefix_execution=False),
            "semantic": SemanticBinaryScorer(backend),
            "json": GeneratedJsonScorer(backend, max_new_tokens=64),
        }
        try:
            saved_rows = load_resume_rows(
                args.output / "rows.jsonl",
                methods=methods,
                case_ids={case.case_id for case in cases},
            )
        except ValueError as exc:
            parser.error(f"cannot resume: {exc}")
        summaries = {}
        with (args.output / "rows.jsonl").open("a") as output:
            for method in methods:
                rows = [row for row in saved_rows if row["method"] == method]
                completed_case_ids = {row["case_id"] for row in rows}
                remaining_cases = [case for case in cases if case.case_id not in completed_case_ids]
                if not remaining_cases:
                    summaries[method] = summarize(rows)
                    emit_event(args, "method_done", method=method, summary=summaries[method])
                    continue
                backend.clear_repeated_state_cache()
                scorer = scorers[method]
                emit_event(
                    args,
                    "phase",
                    method=method,
                    status=f"Warmup {method} (excluded from measurements; "
                    f"{len(candidates) if method == 'semantic' else 1} candidate evaluations)...",
                )
                scorer.score(
                    ChoiceRequest(remaining_cases[0].state, question.instructions, candidates)
                )
                emit_event(
                    args,
                    "method_start",
                    method=method,
                    total=len(cases),
                    completed=len(rows),
                    correct=sum(row["correct"] for row in rows),
                )
                for case in remaining_cases:
                    emit_event(
                        args,
                        "case_start",
                        method=method,
                        case_id=case.case_id,
                        completed=len(rows),
                        total=len(cases),
                    )
                    backend.reset_runtime_metrics()
                    request = ChoiceRequest(
                        case.state, question.instructions, candidates, case.case_id
                    )
                    started = time.perf_counter()
                    error = None
                    try:
                        result = scorer.score(request).to_dict()
                    except Exception as exc:  # noqa: BLE001 -- retain failed cases in the denominator
                        result, error = {}, f"{type(exc).__name__}: {exc}"
                    latency = (time.perf_counter() - started) * 1000
                    choice = result.get("choice")
                    expected = case.expected[question.id]
                    row = {
                        "method": method,
                        "case_id": case.case_id,
                        "expected": expected,
                        "choice": choice,
                        "correct": choice == expected,
                        "valid": error is None and result.get("valid", True),
                        "latency_ms": latency,
                        "runtime": backend.runtime_metrics(),
                        "result": result,
                        "error": error,
                    }
                    output.write(json.dumps(row) + "\n")
                    output.flush()
                    rows.append(row)
                    emit_event(
                        args,
                        "case",
                        method=method,
                        completed=len(rows),
                        total=len(cases),
                        case_id=case.case_id,
                        correct=row["correct"],
                        valid=row["valid"],
                        choice=choice,
                        expected=expected,
                        error=error,
                        latency_ms=latency,
                        accuracy=sum(item["correct"] for item in rows) / len(rows),
                    )
                    summaries[method] = summarize(rows)
                    (args.output / "summary.json").write_text(json.dumps(summaries, indent=2))
                summaries[method] = summarize(rows)
                (args.output / "summary.json").write_text(json.dumps(summaries, indent=2))
                emit_event(args, "method_done", method=method, summary=summaries[method])
        (args.output / "summary.json").write_text(json.dumps(summaries, indent=2))
        if not args.events_json:
            print(json.dumps(summaries, indent=2))
    finally:
        backend.close()


if __name__ == "__main__":
    main()
