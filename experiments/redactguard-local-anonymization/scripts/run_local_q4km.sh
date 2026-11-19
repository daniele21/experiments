#!/usr/bin/env bash
# Sequential local campaign: realistic + challenge + healthcare + ambiguous.
# Pass any subset of these dataset names as arguments to run only that subset.
set -Eeuo pipefail
EXPERIMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$EXPERIMENT_DIR"
REGISTRY="$EXPERIMENT_DIR/config/models-local-q4km.yaml"
export LOCAL_LLM_REGISTRY_PATHS="${LOCAL_LLM_REGISTRY_PATHS:+$LOCAL_LLM_REGISTRY_PATHS:}$REGISTRY"
MODELS="gemma-4-e4b-it-q4km,qwen3.5-2b-q4km,nemotron-nano-4b"
if (( $# == 0 )); then
  set -- realistic challenge healthcare ambiguous
fi
# Validate all arguments before starting a potentially long campaign.
for dataset in "$@"; do
  case "$dataset" in
    realistic|challenge|healthcare|ambiguous) ;;
    *) printf 'Unknown dataset: %s\n' "$dataset" >&2; exit 2 ;;
  esac
done
for dataset in "$@"; do
  config="config/suite-$dataset.yaml"
  if [[ "$dataset" == realistic ]]; then config=config/suite.yaml; fi
  printf '\nStarting %s: %s\n' "$dataset" "$MODELS"
  uv run --frozen redact-bench suite --config "$config" \
    --models "$MODELS" --no-ensure-models
done
