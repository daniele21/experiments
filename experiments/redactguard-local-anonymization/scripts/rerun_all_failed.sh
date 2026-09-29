#!/usr/bin/env bash
# ==============================================================================
# Rerun all failed cases for each respective model
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=== Rerunning all failed cases per model ==="
uv run python scripts/run_remediation.py --target all "$@"
