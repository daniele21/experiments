# ruff: noqa: C408 - diagnostic script keeps compact dict builders readable
"""Compare three thinking policies on identical public routing cases.

Owns only its dedicated Korgis process group and ports. Saves incremental,
separate evidence; never appends to the main benchmark reports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_bench.benchmark_data import balanced_banking77_cases, banking77_question
from jev_bench.providers.korgis import KorgisController, KorgisProvider

SAMPLING = dict(
    temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repeat_penalty=1.0
)
VARIANTS = {
    "sampling": dict(max_tokens=4096, ctx_size=8192, timeout=360, reasoning_budget=-1),
    "extended": dict(max_tokens=8192, ctx_size=16384, timeout=600, reasoning_budget=-1),
    "bounded": dict(max_tokens=4096, ctx_size=8192, timeout=360, reasoning_budget=3000),
}


def get_json(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def port_free(port):
    with socket.socket() as probe:
        # Completed HTTP connections may remain in TIME_WAIT after the listener
        # has closed. Match the server's reuse behavior without allowing a
        # second listener on an occupied port.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))


def stop_owned(process):
    # Korgis workers create their own sessions. Discover descendants while their
    # parent is still alive; never identify ownership by executable name/port.
    snapshot = subprocess.check_output(["ps", "-axo", "pid=,ppid=,pgid="], text=True)
    rows = [tuple(map(int, line.split())) for line in snapshot.splitlines() if line.strip()]
    owned = {process.pid}
    while True:
        children = {pid for pid, parent, _ in rows if parent in owned}
        if children <= owned:
            break
        owned.update(children)
    groups = {group for pid, _, group in rows if pid in owned and group in owned}
    groups.add(process.pid)
    for group in groups:
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    # A parent may exit before its child. Recheck live owned members rather
    # than signalling stale groups after a successful graceful shutdown.
    def remaining_groups():
        current = subprocess.check_output(["ps", "-axo", "pid=,pgid=,stat="], text=True)
        return {
            int(group)
            for line in current.splitlines() if line.strip()
            for pid, group, state in [line.split()]
            if int(pid) in owned and int(group) in groups and not state.startswith("Z")
        }

    for group in remaining_groups():
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # macOS can report EPERM for an already disappearing process group.
            if group in remaining_groups():
                raise


def main():
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.5-9b-q4km")
    parser.add_argument("--cases", type=int, default=3)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--port", type=int, default=1236)
    parser.add_argument("--backend-port", type=int, default=8092)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--korgis-dir", type=Path, default=ROOT.parents[1] / "korgis")
    parser.add_argument("--binary", default="/opt/homebrew/bin/llama-server")
    args = parser.parse_args()
    if not 1 <= args.cases <= 77:
        parser.error("--cases must be between 1 and 77")
    help_text = subprocess.check_output(
        [args.binary, "--help"], text=True, stderr=subprocess.STDOUT
    )
    if "bounded" in args.variants and "--reasoning-budget N" not in help_text:
        parser.error("Installed llama-server does not advertise --reasoning-budget")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or ROOT / "results" / "thinking" / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = balanced_banking77_cases(ROOT / "data/cache", max_cases=77, seed=42)[: args.cases]
    question = banking77_question(ROOT / "data/cache")
    manifest = dict(
        model=args.model,
        seed=42,
        sampling=SAMPLING,
        variants={name: VARIANTS[name] for name in args.variants},
        cases=[
            dict(id=c.case_id, state=c.state, expected=c.expected, metadata=c.metadata)
            for c in cases
        ],
        binary=args.binary,
        korgis_dir=str(args.korgis_dir),
        started_at=stamp,
        scope="small diagnostic sample, not benchmark accuracy",
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Evidence: {output}", flush=True)
    records = []
    for name in args.variants:
        config = VARIANTS[name]
        backend_port = args.backend_port
        for port in (args.port, args.backend_port):
            port_free(port)
        env = os.environ.copy()
        env.update(
            LOCAL_LLM_REGISTRY_PATHS=str(ROOT / "benchmark-models.yaml"),
            LOCAL_LLM_SERVER_BIN=args.binary,
            LLAMA_ARG_REASONING="on",
            LLAMA_ARG_THINK="deepseek",
            LLAMA_ARG_THINK_BUDGET=str(config["reasoning_budget"]),
            LLAMA_ARG_THINK_BUDGET_MESSAGE="",
        )
        command = [
            str(args.korgis_dir / ".venv/bin/python"),
            "-m",
            "local_llm_server",
            "serve",
            "--model",
            args.model,
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--llama-server-port",
            str(args.backend_port),
            "--llama-server-bin",
            args.binary,
            "--ctx-size",
            str(config["ctx_size"]),
            "--enable-thinking",
            "--no-download",
            "--enable-admin-api",
        ]
        base = f"http://127.0.0.1:{args.port}"
        print(f"Starting {name}: {config}", flush=True)
        with (output / f"{name}.log").open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=args.korgis_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 180
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Korgis exited ({process.returncode}); see {name}.log")
                    try:
                        if get_json(base + "/health").get("ok"):
                            break
                    except (OSError, ValueError):
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("Korgis startup deadline exceeded")
                    time.sleep(1)
                # Korgis may move its private port when the preferred one is in
                # TIME_WAIT. Read the actual endpoint from this owned run's log.
                endpoints = re.findall(
                    r"llama-server ready on http://127\.0\.0\.1:(\d+)",
                    (output / f"{name}.log").read_text(),
                )
                if not endpoints:
                    raise RuntimeError("No observed backend endpoint in the owned runtime log")
                backend_port = int(endpoints[-1])
                props = get_json(f"http://127.0.0.1:{backend_port}/props")
                (output / f"{name}-backend-props.json").write_text(json.dumps(props, indent=2))
                if props.get("default_generation_settings", {}).get("n_ctx") != config["ctx_size"]:
                    raise RuntimeError("Backend context does not match the comparison policy")
                identity = KorgisController(base + "/v1").identity()
                (output / f"{name}-identity.json").write_text(json.dumps(identity, indent=2))
                provider = KorgisProvider(
                    args.model,
                    base + "/v1",
                    seed=42,
                    enable_thinking=True,
                    max_tokens=config["max_tokens"],
                    timeout=config["timeout"],
                    sampling=SAMPLING,
                )
                try:
                    for case in cases:
                        print(f"  {name}: {case.case_id} running", flush=True)
                        result = provider.evaluate(case.state, [question])
                        slots = get_json(f"http://127.0.0.1:{backend_port}/slots")
                        (output / f"{name}-{case.case_id}-slots.json").write_text(
                            json.dumps(slots, indent=2)
                        )
                        raw = result.raw.model_dump(mode="json") if result.raw is not None else {}
                        choice = (raw.get("choices") or [{}])[0]
                        message = choice.get("message") or {}
                        actual = result.answers.get("intent")
                        record = dict(
                            variant=name,
                            case_id=case.case_id,
                            valid=result.valid,
                            correct=result.valid
                            and actual is not None
                            and actual.value == case.expected["intent"],
                            actual=actual.value if actual else None,
                            expected=case.expected["intent"],
                            latency_ms=result.latency_ms,
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            error=result.error,
                            finish_reason=choice.get("finish_reason"),
                            content_chars=len(message.get("content") or ""),
                            reasoning_chars=len(message.get("reasoning_content") or ""),
                        )
                        records.append(record)
                        with (output / "results.jsonl").open("a") as stream:
                            stream.write(json.dumps(record) + "\n")
                        # Explicit public-dataset diagnostic artifact; not general server logging.
                        (output / f"{name}-{case.case_id}.json").write_text(
                            json.dumps(raw, indent=2)
                        )
                        print(json.dumps(record), flush=True)
                finally:
                    provider.client.close()
            finally:
                stop_owned(process)
                deadline = time.monotonic() + 10
                for port in (args.port, backend_port):
                    while True:
                        try:
                            port_free(port)
                            break
                        except OSError:
                            if time.monotonic() > deadline:
                                raise RuntimeError(f"Owned listener {port} did not close")
                            time.sleep(0.2)
        summary = {}
        for variant in args.variants:
            rows = [r for r in records if r["variant"] == variant]
            if rows:
                summary[variant] = dict(
                    cases=len(rows),
                    valid=sum(r["valid"] for r in rows),
                    correct=sum(r["correct"] for r in rows),
                    mean_seconds=sum(r["latency_ms"] for r in rows) / len(rows) / 1000,
                    output_tokens=[r["output_tokens"] for r in rows],
                )
        (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
