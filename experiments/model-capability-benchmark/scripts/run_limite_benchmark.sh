#!/usr/bin/env bash
# ==============================================================================
# Model Capability Benchmark - Paradigma Limite 1B Violetto Launcher
#
# Runs benchmarks against Paradigma Limite 1B Violetto on mathematical reasoning.
#
# Recommended server:
#   VLLM_PLUGINS=limite uv run vllm serve paradigma-inc/limite-1b-violetto --port 8000
#
# Usage:
#   ./scripts/run_limite_benchmark.sh
#   PROFILE=core ./scripts/run_limite_benchmark.sh
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ------------------------------------------------------------------------------
# Load .env if present
# ------------------------------------------------------------------------------
if [ -f "${BENCHMARK_DIR}/.env" ]; then
  set -a
  source "${BENCHMARK_DIR}/.env"
  set +a
fi

# ------------------------------------------------------------------------------
# Configuration & Defaults
# ------------------------------------------------------------------------------
MODEL="${MODEL:-limite-1b-violetto}"
CAPABILITIES="${CAPABILITIES:-mathematics}"
PROFILE="${PROFILE:-smoke}"

export VLLM_BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1}"
export MCB_RESOURCE_TELEMETRY="${MCB_RESOURCE_TELEMETRY:-1}"
export MCB_RESOURCE_SAMPLE_INTERVAL_MS="${MCB_RESOURCE_SAMPLE_INTERVAL_MS:-250}"

# Memory cap settings for in-process execution (Apple Silicon MPS / CUDA)
export PYTORCH_MPS_HIGH_WATERMARK_RATIO="${PYTORCH_MPS_HIGH_WATERMARK_RATIO:-0.3}"
export PYTORCH_MPS_LOW_WATERMARK_RATIO="${PYTORCH_MPS_LOW_WATERMARK_RATIO:-0.1}"
export BENCH_MAX_MEMORY_GB="${BENCH_MAX_MEMORY_GB:-4.0}"

TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
RUN_GROUP="${RUN_GROUP:-limite-violetto-${TIMESTAMP}}"

echo "=================================================================="
echo "🎯 Model Capability Benchmark: Paradigma Limite 1B Violetto"
echo "=================================================================="
echo "📁 Benchmark Root   : ${BENCHMARK_DIR}"
echo "🧠 Target Model     : ${MODEL}"
echo "📊 Capabilities     : ${CAPABILITIES}"
echo "⚡ Profile          : ${PROFILE}"
echo "🏷️  Run Group        : ${RUN_GROUP}"
echo "🔌 vLLM Base URL    : ${VLLM_BASE_URL}"
echo "🌡️  Sampling         : temperature=0.6, top_p=0.95 (Paradigma recommended)"
echo "🛡️  Memory Cap       : max_memory_gb=${BENCH_MAX_MEMORY_GB}, mps_watermark=${PYTORCH_MPS_HIGH_WATERMARK_RATIO}"
echo "📈 Telemetry Sample : ${MCB_RESOURCE_SAMPLE_INTERVAL_MS}ms"
echo "=================================================================="

cd "${BENCHMARK_DIR}"

# ------------------------------------------------------------------------------
# Step 1: Healthcheck Server Endpoint (for external models)
# ------------------------------------------------------------------------------
echo ""
if [ "${MODEL}" = "limite-1b-violetto" ]; then
  echo "🩺 [1/5] Execution Mode: In-Process Native PyTorch/Transformers (Metal/CUDA acceleration)."
  echo "✅ No external inference daemon or open network port required."
elif [ "${MODEL}" = "limite-1b-violetto-vllm" ]; then
  echo "🩺 [1/5] Checking vLLM endpoint health (${VLLM_BASE_URL})..."
  HEALTH_URL="${VLLM_BASE_URL}/models"
  if ! curl -fsS "${HEALTH_URL}" > /dev/null 2>&1; then
    echo "❌ Error: Inference server is not responding at ${HEALTH_URL}."
    echo "💡 Start vLLM with: VLLM_PLUGINS=limite uv run vllm serve paradigma-inc/limite-1b-violetto --port 8001"
    exit 1
  fi
  echo "✅ vLLM inference server is online and responding."
else
  echo "🩺 [1/5] Checking endpoint health (${VLLM_BASE_URL})..."
fi

# ------------------------------------------------------------------------------
# Step 2: Preflight Config Validation
# ------------------------------------------------------------------------------
echo ""
echo "🔍 [2/5] Validating model registry configuration..."
uv run model-bench validate-config --models "${MODEL}"

# ------------------------------------------------------------------------------
# Step 3: Plan Benchmark
# ------------------------------------------------------------------------------
echo ""
echo "📋 [3/5] Benchmark execution plan:"
uv run model-bench plan --capabilities "${CAPABILITIES}" --profile "${PROFILE}"

# ------------------------------------------------------------------------------
# Step 4: Run Benchmark
# ------------------------------------------------------------------------------
echo ""
echo "🚀 [4/5] Executing benchmark run..."
uv run model-bench run \
  --models "${MODEL}" \
  --capabilities "${CAPABILITIES}" \
  --profile "${PROFILE}" \
  --run-group "${RUN_GROUP}" \
  --resume \
  --progress

# ------------------------------------------------------------------------------
# Step 5: Refresh Analytics & Dashboard Data
# ------------------------------------------------------------------------------
echo ""
echo "📊 [5/5] Refreshing DuckDB analytics and dashboard data..."
uv run model-bench project --rebuild --export-dashboard

echo ""
echo "=================================================================="
echo "✅ Limite 1B Violetto benchmark completed successfully!"
echo "📈 View results in the local dashboard at: http://localhost:5173"
echo "=================================================================="
