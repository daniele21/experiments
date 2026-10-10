#!/usr/bin/env bash
# Run RedactGuard's full realistic model benchmark on a local Apple Silicon Mac.
# Usage: bash scripts/run_realistic_local.sh [--models ID1,ID2] [--model MODEL]
#                                            [--korgis-repo PATH]
#                                            [--llama-server-bin PATH] [--check-only]
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Run the COMPLETE RedactGuard realistic benchmark against ONLY the requested
Korgis model IDs (quality on all 11 documents, plus configured latency).
With no model arguments, use suite.models from config/suite.yaml.
Run from any directory. Korgis and the local model artifacts must be installed.

  bash scripts/run_realistic_local.sh
  bash scripts/run_realistic_local.sh --check-only
  bash scripts/run_realistic_local.sh --model qwen3.5-4b-q4km
  bash scripts/run_realistic_local.sh --models "qwen3.5-4b-q4km,qwen3.5-9b-q4km"
  bash scripts/run_realistic_local.sh --model nemotron-nano-4b --model nemotron-nano-4b-q8
  bash scripts/run_realistic_local.sh --korgis-repo "$HOME/Personal/korgis"

Options:
  --model MODEL             Add a single Korgis model ID (repeatable).
  --models ID1,ID2          Explicit comma-separated model IDs. May combine
                            with --model; duplicates are removed.
  --korgis-repo PATH        Path to an existing Korgis/local-llm-server clone.
  --llama-server-bin PATH   Path to a compatible llama-server executable.
  --check-only             Validate local setup without launching inference.
  --download-missing       Opt in to model downloads (never default).
  -h, --help               Show this help.

Full suite includes quality and repeated latency evaluations. Results are kept
locally under results/suites/; this script does not upload files to GitHub.
USAGE
}

error() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '[RedactGuard] %s\n' "$*"; }

[[ "$(uname -s)" == "Darwin" ]] || error "This script is intended for macOS on Apple Silicon."
# Rosetta-inherited environments otherwise compile x86_64 wheels.
if [[ "$(uname -m)" != "arm64" ]]; then
  if [[ "${REDACT_ARM64_REEXEC:-0}" == "1" ]]; then
    error "Could not switch to a native ARM64 shell."
  fi
  exec /usr/bin/arch -arm64 /usr/bin/env REDACT_ARM64_REEXEC=1 /bin/bash "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
EXPERIMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
[[ -f "$EXPERIMENT_DIR/config/suite.yaml" && -f "$EXPERIMENT_DIR/pyproject.toml" ]] \
  || error "Run the script from a RedactGuard experiment checkout (missing config/suite.yaml)."

KORGIS_DIR="${KORGIS_REPO:-}"
LLAMA_BIN="${LOCAL_LLM_SERVER_BIN:-}"
CHECK_ONLY=0
DOWNLOAD_MISSING=0
MODELS=()
while (( $# )); do
  case "$1" in
    --model)
      (( $# >= 2 )) || error "Missing value for --model."
      MODELS+=("$2"); shift 2 ;;
    --models)
      (( $# >= 2 )) || error "Missing value for --models."
      [[ -n "$2" ]] || error "--models cannot be empty."
      IFS=',' read -r -a parsed_models <<< "$2"
      MODELS+=("${parsed_models[@]}"); shift 2 ;;
    --korgis-repo)
      (( $# >= 2 )) || error "Missing value for --korgis-repo."
      KORGIS_DIR="$2"; shift 2 ;;
    --llama-server-bin)
      (( $# >= 2 )) || error "Missing value for --llama-server-bin."
      LLAMA_BIN="$2"; shift 2 ;;
    --check-only) CHECK_ONLY=1; shift ;;
    --download-missing) DOWNLOAD_MISSING=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) error "Unknown argument: $1 (see --help)." ;;
  esac
done

# Prefer the Korgis version pinned in the experiments repository.
# The repository root's korgis/ entry is a gitlink; the files exist only after
# the submodule has been initialized. Do not silently fall back to a different
# local clone when this repository's pinned submodule can be initialized.
REPO_ROOT="$(cd "$EXPERIMENT_DIR/../.." && pwd -P)"
if [[ -z "$KORGIS_DIR" ]]; then
  PINNED_KORGIS="$REPO_ROOT/korgis"
  if [[ ! -f "$PINNED_KORGIS/pyproject.toml" && -f "$REPO_ROOT/.gitmodules" ]] \
      && command -v git >/dev/null 2>&1 \
      && [[ "$(git -C "$REPO_ROOT" rev-parse --show-toplevel 2>/dev/null || true)" == "$REPO_ROOT" ]]; then
    info "Initializing the repository-pinned Korgis submodule ..."
    git -C "$REPO_ROOT" submodule update --init --depth 1 -- korgis \
      || error "Unable to initialize pinned Korgis. Check Git/network access, or pass --korgis-repo PATH."
  fi
  if [[ -f "$PINNED_KORGIS/pyproject.toml" && -d "$PINNED_KORGIS/src/local_llm_server" ]]; then
    KORGIS_DIR="$PINNED_KORGIS"
    info "Using repository-pinned Korgis: $PINNED_KORGIS"
  fi
fi

# External Korgis directories are only fallbacks when the repository submodule
# cannot be used (e.g. a source ZIP without Git metadata), or explicit overrides.
if [[ -z "$KORGIS_DIR" ]]; then
  for candidate in \
    "$EXPERIMENT_DIR/../../../korgis" \
    "$EXPERIMENT_DIR/../../../local-llm-server" \
    "$HOME/Personal/korgis" \
    "$HOME/Personal/local-llm-server" \
    "$HOME/korgis" \
    "$HOME/local-llm-server"; do
    if [[ -f "$candidate/pyproject.toml" && -d "$candidate/src/local_llm_server" ]]; then
      KORGIS_DIR="$candidate"
      info "Using external Korgis fallback: $KORGIS_DIR"
      break
    fi
  done
fi
[[ -n "$KORGIS_DIR" ]] || error "Korgis checkout not found. Specify --korgis-repo /absolute/path/to/korgis."
KORGIS_DIR="$(cd "$KORGIS_DIR" && pwd -P)" || error "Invalid Korgis path."
[[ -f "$KORGIS_DIR/pyproject.toml" && -d "$KORGIS_DIR/src/local_llm_server" ]] \
  || error "Not a Korgis checkout: $KORGIS_DIR"
export KORGIS_REPO="$KORGIS_DIR"

command -v uv >/dev/null 2>&1 || error "Install uv first: brew install uv"
UV_BIN="$(command -v uv)"
/usr/bin/arch -arm64 "$UV_BIN" --version >/dev/null 2>&1 \
  || error "uv must support native ARM64. Install it with Homebrew."
uv_native() { /usr/bin/arch -arm64 "$UV_BIN" "$@"; }

# Constrain CPU-related native libraries, without claiming a hard RAM quota.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-4}"
export TOKENIZERS_PARALLELISM=false
export CMAKE_OSX_ARCHITECTURES="arm64"
export ARCHFLAGS="-arch arm64"
# Korgis pins llama-cpp-python. Explicitly configure its native llama.cpp build
# for Apple Silicon and disable optional CURL/link-time TLS dependencies.
export CMAKE_ARGS="${CMAKE_ARGS:--DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_APPLE_SILICON_PROCESSOR=arm64 -DGGML_METAL=ON -DGGML_CURL=OFF -DLLAMA_CURL=OFF}"

# Make sure uv will not pick an inherited Rosetta venv or an x86_64 interpreter.
unset VIRTUAL_ENV PYTHONHOME UV_PYTHON
PYTHON_REQUEST="cpython-3.12-macos-aarch64-none"
info "Resolving a native ARM64 Python 3.12 before building llama-cpp-python ..."
if ! PYTHON_BIN="$(uv_native python find "$PYTHON_REQUEST" 2>/dev/null)"; then
  info "Native ARM64 Python 3.12 not found; installing uv-managed Python (not model weights)."
  uv_native python install "$PYTHON_REQUEST" \
    || error "Unable to provision native ARM64 Python 3.12."
  PYTHON_BIN="$(uv_native python find "$PYTHON_REQUEST")" \
    || error "Unable to locate native ARM64 Python 3.12 after installation."
fi
"$PYTHON_BIN" -c 'import platform, sys; assert platform.machine() == "arm64" and sys.version_info[:2] == (3, 12), (platform.platform(), sys.version)' \
  || error "Selected Python is not native ARM64 CPython 3.12: $PYTHON_BIN"
export UV_PYTHON="$PYTHON_BIN"

cd "$EXPERIMENT_DIR"
info "Experiment: $EXPERIMENT_DIR"
info "Korgis: $KORGIS_DIR"
info "Python: $PYTHON_BIN (native ARM64)"
info "CMake: $CMAKE_ARGS"

# Repair stale environments created under Rosetta before asking CMake to build.
for venv in "$EXPERIMENT_DIR/.venv" "$KORGIS_DIR/.venv"; do
  if [[ -x "$venv/bin/python" ]] \
    && ! "$venv/bin/python" -c 'import platform,sys; sys.exit(0 if platform.machine()=="arm64" and sys.version_info[:2]==(3,12) else 1)' 2>/dev/null; then
    info "Removing incompatible x86_64 / non-3.12 virtualenv: $venv"
    rm -rf -- "$venv" \
      || error "Unable to recreate incompatible Python environment: $venv"
  fi
done

info "Preparing benchmark Python environment ..."
uv_native sync --extra dev --python "$PYTHON_BIN" \
  || error "RedactGuard uv sync failed."

# Save a complete build trace, while surfacing the first *real* compiler/linker
# diagnostics (not trailing CMake install warnings) if Korgis compilation fails.
BUILD_LOG_DIR="$EXPERIMENT_DIR/results/manual-logs"
mkdir -p "$BUILD_LOG_DIR"
BUILD_LOG="$BUILD_LOG_DIR/korgis-install-$(date -u +%Y%m%dT%H%M%SZ).log"
info "Installing pinned Korgis dependencies (full log: $BUILD_LOG) ..."
if ! (cd "$KORGIS_DIR" && uv_native sync --frozen --python "$PYTHON_BIN") >"$BUILD_LOG" 2>&1; then
  echo "" >&2
  echo "Korgis build failed. Compiler and linker errors:" >&2
  grep -inE 'FAILED:|Undefined symbols|symbol\\(s\\) not found|ld: |clang: error|clang\\+\\+: error|fatal error:|error:|failed to build|CMake Error' "$BUILD_LOG" | tail -n 35 >&2 || true
  echo "Last 45 lines of the full build log:" >&2
  tail -n 45 "$BUILD_LOG" >&2
  error "Korgis installation failed. Full diagnostic log: $BUILD_LOG"
fi
info "Korgis dependencies installed."

# Detect an architecture mismatch before launching inference.
for interpreter in "$EXPERIMENT_DIR/.venv/bin/python" "$KORGIS_DIR/.venv/bin/python"; do
  "$interpreter" -c 'import platform,sys; sys.exit(0 if platform.machine()=="arm64" and sys.version_info[:2]==(3,12) else 1)' \
    || error "Non-ARM64 Python environment at $interpreter; check $BUILD_LOG."
done

info "Validating realistic data and the Korgis model registry ..."
uv_native run --frozen redact-bench check-realistic-dataset --dataset-dir data/realistic

if (( ${#MODELS[@]} == 0 )); then
  info "No model override: reading the configured suite model IDs."
  MODEL_CSV="$(uv_native run --frozen python -c 'import yaml; cfg=yaml.safe_load(open("config/suite.yaml", encoding="utf-8")); print(",".join(cfg["suite"]["models"]))')"
  [[ -n "$MODEL_CSV" ]] || error "No model IDs in config/suite.yaml."
  IFS=',' read -r -a MODELS <<< "$MODEL_CSV"
fi
UNIQUE_MODELS=()
for model in "${MODELS[@]}"; do
  # Model IDs are registry keys, not paths/URLs or arbitrary shell expressions.
  [[ "$model" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || error "Invalid Korgis model ID: '$model'"
  already_added=0
  for previous in "${UNIQUE_MODELS[@]}"; do
    if [[ "$previous" == "$model" ]]; then already_added=1; break; fi
  done
  if (( ! already_added )); then UNIQUE_MODELS+=("$model"); fi
done
MODELS=("${UNIQUE_MODELS[@]}")
(( ${#MODELS[@]} > 0 )) || error "You must provide at least one model ID."
MODEL_CSV="$(IFS=,; echo "${MODELS[*]}")"
export REDACT_MODEL_CSV="$MODEL_CSV"

# Verify each artifact locally, without silently downloading large GGUF weights.
if (( DOWNLOAD_MISSING )); then
  info "Model downloads explicitly enabled. Checking/downloading selected models ..."
  for model in "${MODELS[@]}"; do
    (cd "$KORGIS_DIR" && uv_native run --frozen local-llm download "$model")
  done
fi
"$KORGIS_DIR/.venv/bin/python" - <<'PY'
import os
from pathlib import Path
from local_llm_server.config import build_config

missing = []
for name in os.environ["REDACT_MODEL_CSV"].split(","):
    if not name:
        continue
    try:
        conf = build_config(model=name)
        path = conf.get("model_path")
        downloaded = bool(conf.get("model_downloaded"))
        valid = bool(path and Path(path).is_file() and downloaded)
    except Exception as exc:
        print(f"  MODEL {name}: CONFIG ERROR ({type(exc).__name__}: {exc})")
        valid = False
    else:
        print(f"  MODEL {name}: {'READY' if valid else 'NOT FOUND'} (backend: {conf.get('backend', 'unknown')})")
    if not valid:
        missing.append(name)
if missing:
    raise SystemExit("Missing model artifacts: " + ", ".join(missing)
                     + ". Download explicitly using --download-missing or Korgis local-llm download.")
PY

# The RedactGuard suite manages its own Korgis service on localhost:12435.
# It must not reuse, kill or interfere with any unrelated service on this port.
if /usr/sbin/lsof -nP -iTCP:12435 -sTCP:LISTEN -t 2>/dev/null | grep -q .; then
  error "Port 12435 is already listening. Stop the existing process or adjust config/suite.yaml."
fi

# Version verification uses the same Korgis library that enforces the runtime floor.
# Prefer Homebrew llama-server over LM Studio extension builds with unparseable identities.
export REDACT_REQUESTED_LLAMA_BIN="$LLAMA_BIN"
LLAMA_BIN="$("$KORGIS_DIR/.venv/bin/python" - <<'PY'
import os
from pathlib import Path
from local_llm_server.llama_server_compat import validate_llama_server_binary

home = Path.home()
explicit = os.getenv("REDACT_REQUESTED_LLAMA_BIN", "")
if explicit:
    candidates = [Path(explicit).expanduser()]
else:
    candidates = [Path("/opt/homebrew/bin/llama-server"), home / ".local/bin/llama-server",
                  Path("/usr/local/bin/llama-server")]
    candidates.extend(sorted((home / ".lmstudio/extensions/backends").glob("llama.cpp-*/llama-server"), reverse=True))
for path in candidates:
    if not path.is_file() or not os.access(path, os.X_OK):
        continue
    try:
        verdict = validate_llama_server_binary(path)
    except (RuntimeError, OSError):
        continue
    if verdict.supported:
        print(path)
        break
else:
    raise SystemExit("No supported llama-server found (Korgis needs an attributable build >=10621). "
                     "Use --llama-server-bin /path/to/verified/llama-server.")
PY
)" || error "llama-server version check failed."
export LOCAL_LLM_SERVER_BIN="$LLAMA_BIN"
info "Verified llama-server: $LOCAL_LLM_SERVER_BIN"

info "Selected models ONLY: $MODEL_CSV"
info "Dataset: data/realistic (all 11 documents); latency config: config/suite.yaml"
if (( CHECK_ONLY )); then
  info "All setup checks passed; --check-only requested, no inference executed."
  exit 0
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$EXPERIMENT_DIR/results/manual-logs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/realistic-$STAMP.log"
info "Starting full realistic benchmark for these ${#MODELS[@]} model(s) (quality + latency), sequentially."
info "Log: $RUN_LOG"
info "Use Ctrl+C to interrupt. Raw results stay on this Mac."

# Pipefail preserves the true benchmark exit status while tee saves logs.
# Korgis is owned/stopped by redact-bench's managed suite.
SUITE_ARGS=(suite --config "$EXPERIMENT_DIR/config/suite.yaml" --korgis-repo "$KORGIS_DIR" --models "$MODEL_CSV")
if (( DOWNLOAD_MISSING )); then
  SUITE_ARGS+=(--ensure-models)
else
  SUITE_ARGS+=(--no-ensure-models)
fi
if ! uv_native run --frozen redact-bench "${SUITE_ARGS[@]}" 2>&1 | tee "$RUN_LOG"; then
  error "Benchmark failed. Inspect $RUN_LOG and the latest results/suites/*/logs/*.log for Korgis errors."
fi
info "Benchmark finished. Results: $EXPERIMENT_DIR/results/suites"
info "To inspect results: (cd '$EXPERIMENT_DIR' && uv run redact-bench ui)"
