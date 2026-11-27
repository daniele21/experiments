#!/usr/bin/env bash
# Run against the exact, already-downloaded Qwen3.8-27B UD-Q4_K_M GGUF.
# Never download or replace model weights, and do not change standard suite settings.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="qwen3.8-27b-ud-q4km"
GGUF="$HOME/.lmstudio/models/unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf"
EXPECTED="322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482"
PROFILE="${PROFILE:-smoke}"
case "$PROFILE" in smoke|core) ;; *) echo "PROFILE must be smoke or core" >&2; exit 2;; esac
test -f "$GGUF" || { echo "Missing local Qwen3.8 GGUF: $GGUF" >&2; exit 2; }
ACTUAL="$(shasum -a 256 "$GGUF" | awk '{print $1}')"
[[ "$ACTUAL" == "$EXPECTED" ]] || {
  echo "GGUF revision mismatch: $ACTUAL (expected $EXPECTED). Do not silently replace or relabel the artifact." >&2
  exit 2
}
export KORGIS_BASE_URL="${KORGIS_BASE_URL:-http://127.0.0.1:1235/v1}"
export KORGIS_CONTROL_TIMEOUT_SECONDS="${KORGIS_CONTROL_TIMEOUT_SECONDS:-660}"
export MCB_RESOURCE_TELEMETRY=1
export MCB_RESOURCE_SAMPLE_INTERVAL_MS="${MCB_RESOURCE_SAMPLE_INTERVAL_MS:-250}"
CAMPAIGN="${CAMPAIGN:-qwen38-27b-ud-q4km-$(date -u +%Y%m%dT%H%M%SZ)}"
cd "$ROOT"
curl -fsS "${KORGIS_BASE_URL%/v1}/health" >/dev/null
uv run model-bench validate-config --models "$MODEL"
uv run model-bench plan --capabilities all --profile "$PROFILE"
for CAP in structured-output qa-abstention mathematical-reasoning intent-classification oos-calibration; do
  RUN_ID="$CAMPAIGN-$CAP-$PROFILE"
  args=(--models "$MODEL" --capabilities "$CAP" --profile "$PROFILE" --run-group "$CAMPAIGN" --run-id "$RUN_ID" --resume --progress)
  if [[ "$PROFILE" == smoke ]]; then
    args+=(--output-dir "results/scratch/$RUN_ID")
  fi
  uv run model-bench run "${args[@]}"
done
if [[ "$PROFILE" == core ]]; then
  uv run model-bench project --rebuild --export-dashboard
fi
