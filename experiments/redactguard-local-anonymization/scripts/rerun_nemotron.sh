#!/usr/bin/env bash
# ==============================================================================
# Rerun Nemotron models on failing dense documents
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "=== Rerunning Nemotron (4B) on failing dense documents ==="
uv run python scripts/run_remediation.py --target nemotron "$@"
