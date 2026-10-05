#!/usr/bin/env bash
# ==============================================================================
# Model Capability Benchmark - Classification Suite Launcher
#
# Runs classification capabilities (intent-classification, oos-calibration)
# across Decisio decision models and/or reference LLMs sequentially on Metal/GPU.
#
# Supported models evaluated in jev-vs-llm:
#   - decisio-qwen3.5-2b-q4km
#   - decisio-qwen3.5-4b-q4km
#   - decisio-qwen3.5-9b-q4km
#   - jev-1.13.0 (TypeSafe System 1)
#   - qwen3.5-2b-q4km / qwen3.5-4b-q4km / qwen3.5-9b-q4km (via Korgis local-llm)
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Configuration & Defaults
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Target models to evaluate (comma-separated or CLI override)
MODELS="${MODELS:-decisio-qwen3.5-2b-q4km,decisio-qwen3.5-4b-q4km,decisio-qwen3.5-9b-q4km}"

# Classification-only capabilities
CAPABILITIES="${CAPABILITIES:-intent-classification,oos-calibration}"

# Benchmark profile: smoke (77/80 cases), core (154 cases), or extended
PROFILE="${PROFILE:-smoke}"

# Run group tag for aggregated observability
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
RUN_GROUP="${RUN_GROUP:-decisio-classification-${TIMESTAMP}}"

# Decisio backend options
export DECISIO_ROOT="${DECISIO_ROOT:-$(cd "${BENCHMARK_DIR}/../../decisio" 2>/dev/null && pwd || echo "${HOME}/Personal/decisio")}"
export DECISIO_PYTHON="${DECISIO_PYTHON:-${DECISIO_ROOT}/.venv/bin/python}"
export DECISIO_DEVICE="${DECISIO_DEVICE:-metal}"
export DECISIO_THREADS="${DECISIO_THREADS:-4}"

echo "=================================================================="
echo "🎯 Model Capability Benchmark: Classification Suite"
echo "=================================================================="
echo "📁 Benchmark Root : ${BENCHMARK_DIR}"
echo "🧠 Target Models  : ${MODELS}"
echo "📊 Capabilities   : ${CAPABILITIES}"
echo "⚡ Profile        : ${PROFILE}"
echo "🏷️  Run Group      : ${RUN_GROUP}"
echo "⚙️  Decisio Root   : ${DECISIO_ROOT}"
echo "🍏 Decisio Device : ${DECISIO_DEVICE}"
echo "=================================================================="

cd "${BENCHMARK_DIR}"

# ------------------------------------------------------------------------------
# Step 1: Preflight & Config Validation
# ------------------------------------------------------------------------------
echo ""
echo "🔍 [1/4] Validating model configurations and environment..."
uv run model-bench validate-config --models "${MODELS}"

echo ""
echo "📋 [2/4] Benchmark execution plan:"
uv run model-bench plan --capabilities "${CAPABILITIES}" --profile "${PROFILE}"

# ------------------------------------------------------------------------------
# Step 2: Sequential Execution
# Running models sequentially ensures resident GGUFs on Apple Metal
# do not contend for unified memory.
# ------------------------------------------------------------------------------
echo ""
echo "🚀 [3/4] Executing classification benchmark matrix..."

IFS=',' read -ra MODEL_ARRAY <<< "${MODELS}"
TOTAL_MODELS="${#MODEL_ARRAY[@]}"
CURRENT_INDEX=0

for MODEL in "${MODEL_ARRAY[@]}"; do
  CURRENT_INDEX=$((CURRENT_INDEX + 1))
  MODEL="$(echo "${MODEL}" | xargs)" # trim whitespace
  echo ""
  echo "------------------------------------------------------------------"
  echo "▶️  [${CURRENT_INDEX}/${TOTAL_MODELS}] Running model: ${MODEL}"
  echo "------------------------------------------------------------------"

  uv run model-bench run \
    --models "${MODEL}" \
    --capabilities "${CAPABILITIES}" \
    --profile "${PROFILE}" \
    --run-group "${RUN_GROUP}" \
    --resume \
    --progress
done

# ------------------------------------------------------------------------------
# Step 3: Analytics Projection & Dashboard Sync
# Refresh DuckDB analytics database and export JSON for Vite UI
# ------------------------------------------------------------------------------
echo ""
echo "📊 [4/4] Refreshing DuckDB analytics and dashboard data..."
uv run model-bench project --rebuild --export-dashboard

echo ""
echo "=================================================================="
echo "✅ Classification benchmark matrix completed successfully!"
echo "📈 View results in the local dashboard at: http://localhost:5173"
echo "=================================================================="
