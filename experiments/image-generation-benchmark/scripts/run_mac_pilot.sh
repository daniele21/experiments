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
    --profile pilot --output-dir "$OUTPUT/results" --dry-run
) | tee "$OUTPUT/dry-run.txt"

if [[ "${BENCHMARK_MODE:-preflight}" == preflight ]]; then
  echo "PILOT_PREFLIGHT_OK: four-category run plan resolved; no image inference performed"
  printf '{"status":"preflight_passed","profile":"pilot","expected_images":4,"inference_calls":0,"korgis_sha":"%s","experiments_sha":"%s"}\n' \
    "$KORGIS_SOURCE_SHA" "$EXPERIMENTS_SOURCE_SHA" > "$OUTPUT/summary.json"
  exit 0
fi
[[ "${BENCHMARK_MODE:-}" == pilot ]] || { echo "::error::Unsupported mode"; exit 2; }

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

# Process RSS is an observation of the owned native sd-server process.
# It is NOT overall Apple unified memory, Metal allocation, or peak GPU usage.
(
  set +e
  max_rss_kib=0
  while kill -0 "$KORGIS_PID" 2>/dev/null; do
    pid="$(lsof -nP -t -iTCP:$SD_PORT -sTCP:LISTEN 2>/dev/null | head -n 1)"
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      rss_kib="$(ps -o rss= -p "$pid" 2>/dev/null | tr -d '[:space:]')"
      if [[ "$rss_kib" =~ ^[0-9]+$ && "$rss_kib" -gt "$max_rss_kib" ]]; then
        max_rss_kib="$rss_kib"
        printf '%s\n' "$max_rss_kib" > "$OUTPUT/max_sd_server_rss_kib.txt"
      fi
    fi
    sleep 2
  done
) &
SAMPLER_PID=$!

start_epoch="$(date +%s)"
(
  cd "$EXPERIMENTS_ROOT"
  uv run --frozen python scripts/run_benchmark.py \
    --models qwen-image-2.1-turbo-gguf-q4km \
    --profile pilot --output-dir "$OUTPUT/results"
)
end_epoch="$(date +%s)"
export BENCHMARK_ELAPSED_SECONDS="$((end_epoch-start_epoch))"
kill "$SAMPLER_PID" 2>/dev/null || true
wait "$SAMPLER_PID" 2>/dev/null || true

python3 - <<'PY'
import csv
import json
import os
from pathlib import Path
from statistics import mean, median
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
rss_path = out / "max_sd_server_rss_kib.txt"
if rss_path.is_file():
    summary["max_sd_server_rss_gib"] = round(
        int(rss_path.read_text().strip()) / 1024 / 1024, 2
    )
(out/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
print("KORGIS_EXPERIMENTS_PILOT_PASS", json.dumps(summary), flush=True)
PY
