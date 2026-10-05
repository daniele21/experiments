"""Decisio worker process for model-capability-benchmark.

Runs inside Decisio's dedicated virtualenv with in-process llama-cpp-python.
Listens on stdin for JSON requests, outputs JSON lines on stdout.
"""
from __future__ import annotations

import json
import sys
import time


def main() -> None:
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: decisio_worker.py <decisio_root> <gguf_path> [device] [threads]\n")
        sys.exit(1)

    decisio_root = sys.argv[1]
    gguf_path = sys.argv[2]
    device = sys.argv[3] if len(sys.argv) > 3 else "metal"
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    sys.path.insert(0, f"{decisio_root}/src")
    from decisio.backends.llama_cpp import LlamaCppBackend, LlamaCppBackendConfig
    from decisio.baselines.generation import GeneratedJsonScorer
    from decisio.schema import Candidate, ChoiceRequest

    config = LlamaCppBackendConfig(
        model=gguf_path,
        device=device,
        n_ctx=2048,
        n_batch=512,
        n_ubatch=512,
        n_threads=threads,
        n_threads_batch=threads,
    )
    backend = LlamaCppBackend(config)
    backend.tokenizer.encode("warmup")
    scorer = GeneratedJsonScorer(backend, max_new_tokens=64)

    # Signal ready to parent process
    sys.stdout.write(json.dumps({"status": "ready"}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_data: dict = {}
        try:
            req_data = json.loads(line)
            req_id = req_data.get("request_id")
            state = req_data.get("state") or {}
            question = req_data.get("question", "Classify intent")
            raw_candidates = req_data.get("candidates", [])
            candidates = tuple(Candidate(k, v) for k, v in raw_candidates)

            choice_req = ChoiceRequest(state, question, candidates, req_id)
            started = time.perf_counter()
            result = scorer.score(choice_req)
            dt_ms = (time.perf_counter() - started) * 1000

            resp = {
                "request_id": req_id,
                "choice": result.choice,
                "valid": getattr(result, "valid", True),
                "generated_tokens": getattr(result, "generated_tokens", 0),
                "latency_ms": dt_ms,
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            err_resp = {
                "request_id": req_data.get("request_id"),
                "error": f"{type(exc).__name__}: {exc}",
                "valid": False,
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
