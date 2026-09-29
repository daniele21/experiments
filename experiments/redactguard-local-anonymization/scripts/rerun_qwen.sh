#!/usr/bin/env bash
# ==============================================================================
# Rerun Qwen models on failed document (tabella_piccola.xlsx)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=== Rerunning Qwen models on tabella_piccola.xlsx ==="
uv run python scripts/run_remediation.py --target qwen "$@"
