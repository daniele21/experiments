#!/usr/bin/env bash
# Source-owned, pinned, local-only benchmark of Korgis via the Experiments image-generation suite.
# Korgis is only the local inference provider. The shared Mac action only invokes this script.
set -euo pipefail

: "${KORGIS_SOURCE_SHA:?Pin the Korgis commit before running}"
: "${EXPERIMENTS_SOURCE_SHA:?Pin the Experiments commit before running}"

# Paths are derived from the owner repository, not the runner infrastructure.
EXPERIMENTS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPERIMENTS_REPO="$(cd "$EXPERIMENTS_ROOT/../.." && pwd)"
KORGIS_ROOT="${KORGIS_ROOT:-$(cd "$EXPERIMENTS_REPO/.." && pwd)/korgis}"
OUTPUT="${BENCHMARK_OUTPUT_DIR:-$EXPERIMENTS_ROOT/outputs/mac-pilot}"
export BENCHMARK_OUTPUT_DIR="$OUTPUT"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-pilot}"
case "$BENCHMARK_PROFILE" in
  canary) EXPECTED_IMAGES=1 ;;
  pilot) EXPECTED_IMAGES=4 ;;
  *) echo "::error::Unsupported benchmark profile"; exit 2 ;;
esac
export BENCHMARK_PROFILE EXPECTED_IMAGES
if [[ "${BENCHMARK_MODE:-preflight}" != preflight && "${BENCHMARK_MODE:-}" != "$BENCHMARK_PROFILE" ]]; then
  echo "::error::Benchmark mode must match profile"; exit 2
fi
BIN="$HOME/.local-llm/tools/sdcpp-b43af40461cc64c89cac3b621019f8914f50dd9c/build/bin/sd-server"
MODEL_ROOT="$HOME/.local-llm/models/qwen-image-2.1-turbo-gguf-q4km"
PORT=18735
SD_PORT=18736
export KORGIS_BASE_URL="http://127.0.0.1:$PORT"
export OPENAI_API_KEY="" GEMINI_API_KEY="" ANTHROPIC_API_KEY=""

mkdir -p "$OUTPUT"
[[ "$(git -C "$KORGIS_ROOT" rev-parse HEAD)" == "$KORGIS_SOURCE_SHA" ]] || exit 2
[[ "$(git -C "$EXPERIMENTS_REPO" rev-parse HEAD)" == "$EXPERIMENTS_SOURCE_SHA" ]] || exit 2

# Keep the exact pinned native engine and existing local model bundle.
[[ -x "$BIN" ]] || { echo "::error::Pinned native sd-server missing"; exit 2; }
[[ "$(shasum -a 256 "$BIN" | awk '{print $1}')" == "1b2708f81c36ca5b492221a3f221cad1be0c4a748a04be66340e34fa4e4e02a4" ]] || {
  echo "::error::Native runtime SHA256 mismatch"; exit 2;
}
for file in \
  diffusion/qwen-image-2.1-turbo-Q4_K_M.gguf \
  text_encoder/Qwen3-VL-8B-Instruct-UD-Q4_K_XL.gguf \
  vae/qwen_image_2.1_vae_bf16.safetensors; do
  [[ -s "$MODEL_ROOT/$file" ]] || { echo "::error::Missing local artifact: $file"; exit 2; }
done

command -v uv >/dev/null || { echo "::error::Missing uv toolchain on runner"; exit 2; }
if [[ -x "$HOME/.local-llm/tools/cmake-3.31.6/CMake.app/Contents/bin/cmake" ]]; then
  export PATH="$HOME/.local-llm/tools/cmake-3.31.6/CMake.app/Contents/bin:$PATH"
fi

# A dry run validates profile+provider mapping with zero image-generation calls.
(
  cd "$EXPERIMENTS_ROOT"
  uv run --frozen python scripts/run_benchmark.py \
    --models qwen-image-2.1-turbo-gguf-q4km \
    --profile "$BENCHMARK_PROFILE" --output-dir "$OUTPUT/results" --dry-run
) | tee "$OUTPUT/dry-run.txt"

# Real admission, without loading a model or accessing any cloud provider.
# Uses Korgis' actual macOS guard and working-set estimate. A refused load
# stops the benchmark before it consumes further RAM.
(
  cd "$KORGIS_ROOT"
  uv run --frozen python - <<'PY'
import json
from local_llm_server.config import build_config
from local_llm_server.product_runtime import ResourcePolicySettings, build_resource_manager
from local_llm_server.runtime import ModelRuntimeManager, ResourceAdmissionError

cfg = build_config("qwen-image-2.1-turbo-gguf-q4km")
resources = build_resource_manager(ResourcePolicySettings.from_environment())
assert resources is not None and resources.host_protection_enabled, (
    "Mac admission guard must be enabled for a local GPU benchmark"
)
runtime_manager = ModelRuntimeManager(resource_manager=resources)
status = resources.host_memory_status()
reservation = None
decision = "rejected"
reason = "unknown"
try:
    reservation = runtime_manager._reserve_runtime_load(cfg["model"], cfg)
    decision = "admitted"
    reason = cfg.get("resource_admission", {}).get("reason") or "host admission passed"
except ResourceAdmissionError as exc:
    reason = exc.result.reason
finally:
    if reservation is not None:
        resources.release(reservation)
print(json.dumps({
    "decision": decision, "reason": reason,
    "model_key": cfg["model"],
    "estimate_bytes": cfg.get("resource_estimate_bytes"),
    "profile": cfg.get("resource_admission_profile"),
    "host_memory": status,
}), flush=True)
if decision != "admitted":
    raise SystemExit(2)
PY
) | tee "$OUTPUT/admission-probe.json"

if [[ "${BENCHMARK_MODE:-preflight}" == preflight ]]; then
  echo "IMAGEGEN_PREFLIGHT_OK profile=$BENCHMARK_PROFILE cases=$EXPECTED_IMAGES; no inference"
  printf '{"status":"preflight_passed","profile":"%s","expected_images":%s,"inference_calls":0,"korgis_sha":"%s","experiments_sha":"%s"}\n' \
    "$BENCHMARK_PROFILE" "$EXPECTED_IMAGES" "$KORGIS_SOURCE_SHA" "$EXPERIMENTS_SOURCE_SHA" > "$OUTPUT/summary.json"
  exit 0
fi
[[ "${BENCHMARK_MODE:-}" == canary || "${BENCHMARK_MODE:-}" == pilot ]] || { echo "::error::Unsupported mode"; exit 2; }

# Fail closed if a port is already occupied; never terminate another server.
python3 - <<'PY'
import socket
for port in (18735, 18736):
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        raise SystemExit(f"Benchmark port {port} unavailable: {exc}")
    finally:
        sock.close()
PY

echo "Starting pinned Korgis; no model downloads permitted"
(
  cd "$KORGIS_ROOT"
  uv run --frozen local-llm serve \
    --model qwen-image-2.1-turbo-gguf-q4km \
    --host 127.0.0.1 --port "$PORT" \
    --sd-server-bin "$BIN" --sd-server-port "$SD_PORT" \
    --no-download
) > "$OUTPUT/korgis.log" 2>&1 &
KORGIS_PID=$!
cleanup() {
  if [[ -n "${SAMPLER_PID:-}" ]]; then
    kill "$SAMPLER_PID" 2>/dev/null || true
  fi
  if kill -0 "$KORGIS_PID" 2>/dev/null; then
    kill "$KORGIS_PID" 2>/dev/null || true
    sleep 2
  fi
}
trap cleanup EXIT

# Limit startup to 6 minutes, including dependency sync and artifact hashing.
ready=0
for _ in $(seq 1 90); do
  if ! kill -0 "$KORGIS_PID" 2>/dev/null; then
    echo "::error::Korgis exited during startup"; tail -n 90 "$OUTPUT/korgis.log"; exit 1
  fi
  if curl --noproxy '*' -fsS --max-time 5 \
    "$KORGIS_BASE_URL/v1/models" > "$OUTPUT/models.json" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 4
done
if [[ "$ready" -ne 1 ]]; then
  echo "::error::Korgis API not ready"; tail -n 90 "$OUTPUT/korgis.log"; exit 1
fi
echo "KORGIS_API_READY at $KORGIS_BASE_URL"

# Sample native process RSS and macOS host reclaimable/swap counters.
# RAM is never increased by the amount of swap used.
python3 scripts/mac_resource_probe.py \
  --port "$SD_PORT" \
  --output "$OUTPUT/mac_resource_samples.jsonl" \
  --interval 3 > "$OUTPUT/resource-probe.log" 2>&1 &
SAMPLER_PID=$!

start_epoch="$(date +%s)"
(
  cd "$EXPERIMENTS_ROOT"
  uv run --frozen python scripts/run_benchmark.py \
    --models qwen-image-2.1-turbo-gguf-q4km \
    --profile "$BENCHMARK_PROFILE" --output-dir "$OUTPUT/results"
)
end_epoch="$(date +%s)"
export BENCHMARK_ELAPSED_SECONDS="$((end_epoch-start_epoch))"
kill "$SAMPLER_PID" 2>/dev/null || true
wait "$SAMPLER_PID" 2>/dev/null || true

(
cd "$EXPERIMENTS_ROOT"
uv run --frozen python - <<'PY'
import csv
import json
import os
from pathlib import Path
from statistics import mean, median

from imagegen_bench.mac_resource_metrics import read_mac_resource_summary
out = Path(os.environ["BENCHMARK_OUTPUT_DIR"])
files = list((out / "results").glob("*/evidence.csv"))
assert len(files) == 1, f"Expected one run, found {len(files)}"
with files[0].open(newline="") as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 4, f"Expected four pilot samples, found {len(rows)}"
assert {r["category"] for r in rows} == {
    "text_rendering", "compositional", "photorealism", "design"
}
assert {r["seed_requested"] for r in rows} == {"42"}
assert all(r["valid"] == "True" for r in rows), "At least one image result is invalid"
assert all(int(r["sample_index"]) == 0 for r in rows)
assert len({r["artifact_sha256"] for r in rows}) == 4, "Not four unique images"
for row in rows:
    path = files[0].parent / row["artifact_path"]
    assert path.is_file(), f"Missing image: {path.name}"
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG data"
latencies = [float(r["latency_ms"])/1000 for r in rows]
summary = {
    "status": "pilot_passed", "profile": "pilot",
    "images": len(rows), "valid_images": len(rows),
    "categories": sorted({r["category"] for r in rows}),
    "seeds": sorted({int(r["seed_requested"]) for r in rows}),
    "mean_latency_seconds": round(mean(latencies), 2),
    "median_latency_seconds": round(median(latencies), 2),
    "min_latency_seconds": round(min(latencies), 2),
    "max_latency_seconds": round(max(latencies), 2),
    "total_benchmark_seconds": int(os.environ["BENCHMARK_ELAPSED_SECONDS"]),
    "korgis_sha": os.environ["KORGIS_SOURCE_SHA"],
    "experiments_sha": os.environ["EXPERIMENTS_SOURCE_SHA"],
    "runner": os.environ.get("RUNNER_NAME"),
    "physical_ram_bytes": int(__import__("subprocess").check_output(
        ["sysctl", "-n", "hw.memsize"], text=True).strip()),
}
memory = read_mac_resource_summary(out / "mac_resource_samples.jsonl")
summary["mac_resource_telemetry"] = memory
if memory.get("sd_server_rss_peak_bytes") is not None:
    summary["max_sd_server_rss_gib"] = round(
        memory["sd_server_rss_peak_bytes"] / 1024**3, 2
    )
(out/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
print("KORGIS_EXPERIMENTS_PILOT_PASS", json.dumps(summary), flush=True)
PY
)
