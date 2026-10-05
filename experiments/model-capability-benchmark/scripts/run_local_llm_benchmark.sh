#!/usr/bin/env bash
# ==============================================================================
# Model Capability Benchmark - Standard Local LLM Launcher (Korgis)
#
# Runs benchmarks against local open-weight models served by the standard
# Korgis inference runtime (OpenAI-compatible /v1/chat/completions) with live
# RAM and CPU resource telemetry.
#
# Defaults to Qwen 3.5 4B (qwen3.5-4b-q4km).
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
# Target model (standard Korgis model key)
MODEL="${MODEL:-qwen3.5-4b-q4km}"

# Capabilities to evaluate (default to intent-classification, or "all" / comma-separated)
CAPABILITIES="${CAPABILITIES:-intent-classification}"

# Benchmark profile: smoke (77 cases), core (canonical 154 cases), or extended
PROFILE="${PROFILE:-smoke}"

# Runtime environment
export KORGIS_BASE_URL="${KORGIS_BASE_URL:-http://127.0.0.1:1235/v1}"
export MCB_RESOURCE_TELEMETRY="${MCB_RESOURCE_TELEMETRY:-1}"
export MCB_RESOURCE_SAMPLE_INTERVAL_MS="${MCB_RESOURCE_SAMPLE_INTERVAL_MS:-250}"

# Run group tag for aggregated analytics
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
RUN_GROUP="${RUN_GROUP:-standard-llm-${TIMESTAMP}}"

echo "=================================================================="
echo "🎯 Model Capability Benchmark: Standard Local LLM (Korgis)"
echo "=================================================================="
echo "📁 Benchmark Root   : ${BENCHMARK_DIR}"
echo "🧠 Target Model     : ${MODEL}"
echo "📊 Capabilities     : ${CAPABILITIES}"
echo "⚡ Profile          : ${PROFILE}"
echo "🏷️  Run Group        : ${RUN_GROUP}"
echo "🔌 Korgis Base URL  : ${KORGIS_BASE_URL}"
echo "📈 Telemetry Sample : ${MCB_RESOURCE_SAMPLE_INTERVAL_MS}ms"
echo "=================================================================="

cd "${BENCHMARK_DIR}"

# ------------------------------------------------------------------------------
# Step 1: Healthcheck Korgis Server
# ------------------------------------------------------------------------------
echo ""
echo "🩺 [1/5] Checking Korgis server health..."
KORGIS_HEALTH_URL="${KORGIS_BASE_URL%/v1}/health"
if ! curl -fsS "${KORGIS_HEALTH_URL}" > /dev/null 2>&1; then
  echo "❌ Error: Korgis server is not responding at ${KORGIS_HEALTH_URL}."
  echo "💡 Start Korgis with: cd /Users/moltisantid/Personal/experiments/korgis && uv run --frozen local-llm serve --enable-admin-api"
  exit 1
fi
echo "✅ Korgis server is online and healthy."

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
echo "✅ Standard LLM benchmark completed successfully!"
echo "📈 View results in the local dashboard at: http://localhost:5173"
echo "=================================================================="
