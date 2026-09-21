# Korgis local-model comparison

The Jev-vs-LLM suite can run the same decision benchmark through **Korgis / Local LLM Server**.

This document explains both the normal path and the fallback path when a GGUF is not already present in the built-in Korgis registry.

## Local matrix

| Korgis registry key | Model | Quantization | Provider API fee |
|---|---|---|---:|
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | $0 |
| `minicpm3-4b-q4km` | MiniCPM3-4B | Q4_K_M | $0 |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | $0 |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | $0 |

The matrix intentionally contains three roughly 4B-class models — Qwen3.5-4B, MiniCPM3-4B and Nemotron Nano 4B — plus Qwen3.5-9B as a larger within-family reference.

A zero provider API fee is **not** a zero total-cost-of-ownership claim. Electricity, hardware purchase/amortisation, thermal impact and opportunity cost of the device are outside the current cost model.

---

## 1. Set up Korgis

Clone and install Korgis separately from this benchmark:

```bash
cd ~/dev

git clone https://github.com/daniele21/korgis.git
cd korgis

python3 -m pip install "uv==0.8.13"
uv sync --frozen --extra dev
```

Verify the CLI:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm --help
```

The commands below use `uv run --frozen local-llm` so they always execute the Korgis environment from this checkout.

### Install the GGUF runtime used by the benchmark

The benchmark model entries use Korgis' managed `llama_server` backend, so a `llama-server` executable must also be installed.

On macOS/Linux with Homebrew:

```bash
brew install llama.cpp
command -v llama-server
llama-server --version
```

Optionally pin the binary path for Korgis:

```bash
export LOCAL_LLM_SERVER_BIN="$(command -v llama-server)"
```

Equivalent supported configuration:

```bash
uv run --frozen local-llm serve \
  --model <MODEL_KEY> \
  --llama-server-bin /absolute/path/to/llama-server \
  --enable-admin-api \
  --no-download
```

Korgis and llama.cpp are separate components: installing the Python Korgis environment does not by itself guarantee that the managed `llama-server` binary exists.

> [!TIP]
> Korgis listens on port `1235` by default (as configured in `.env`). If another process is holding the port, identify and terminate it:
> ```bash
> lsof -i :1235
> kill <PID>
> ```

The commands below use `uv run --frozen local-llm` so they always execute the Korgis environment from this checkout.

---

## 2. First check whether the model is already registered

```bash
uv run --frozen local-llm models
```

If a benchmark key is listed, Korgis already knows the source/runtime metadata for that model.

Then use:

```bash
uv run --frozen local-llm download qwen3.5-4b-q4km
uv run --frozen local-llm download minicpm3-4b-q4km
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm download qwen3.5-9b-q4km
```

A built-in or external registry entry can define:

```text
registry key
model_id
filename
url
quantization
backend
runtime params
optional sha256
```

Korgis uses that metadata to download the artifact into its model directory.

If the key is missing, `local-llm download <key>` cannot infer the source automatically. Use one of the custom-model workflows below.

---

## 3. Verify downloaded artifacts

After a model is present locally:

```bash
uv run --frozen local-llm verify-artifact qwen3.5-4b-q4km
```

This computes the actual SHA-256 and stores a local verification receipt.

For reproducible evidence, compare the digest against the checksum supplied by the authoritative GGUF source or the checksum pinned by the model registry.

The current Korgis download and verification commands are separate operations, so verification should be run explicitly after downloading.

---

## 4. Custom GGUF workflow A — manually download and use once

If a model is not in Korgis, download the exact GGUF yourself.

Example pattern:

```bash
mkdir -p ~/models/jev-bench

curl -L \
  "https://huggingface.co/<ORG>/<GGUF_REPO>/resolve/<REVISION>/<FILE>.gguf" \
  -o ~/models/jev-bench/<FILE>.gguf
```

Prefer an immutable revision instead of `main`.

Check its digest:

```bash
shasum -a 256 ~/models/jev-bench/<FILE>.gguf
```

For a one-off runtime test, bind the file directly:

```bash
cd ~/dev/korgis

uv run --frozen local-llm serve \
  --model my-local-model \
  --model-path "$HOME/models/jev-bench/<FILE>.gguf" \
  --backend llama_server \
  --ctx-size 8192 \
  --enable-admin-api \
  --no-download
```

Then check:

```bash
curl http://127.0.0.1:1235/health
curl http://127.0.0.1:1235/v1/models
curl http://127.0.0.1:1235/v1/runtime/identity
```

This direct-path mode is useful for smoke testing, but it is not ideal for the managed multi-model benchmark.

---

## 5. Custom GGUF workflow B — manually download and register it

For repeated benchmark use, give the model a stable Korgis registry key.

Create or extend:

```text
~/.local-llm/models.yaml
```

Example:

```yaml
models:
  my-model-4b-q4km:
    path: "/ABSOLUTE/PATH/my-model-4b-Q4_K_M.gguf"
    model_id: "org/model-4b"
    quantization: "Q4_K_M"
    backend: llama_server
    thinking_mode: none
    params:
      ctx_size: 8192
      startup_timeout: 300
      max_concurrent_requests: 1
      default_temperature: 0.0
      enable_thinking: false
      show_thinking: false
    tags: [local-benchmark, custom, 4b]
```

The user registry is merged on top of the built-in registry.

### LM Studio Local Models (Ready-to-use Registry Configuration)

If you have downloaded GGUF models via LM Studio (typically residing under `~/.lmstudio/models/`), you can register them cleanly. This repository includes a pre-configured registry file [benchmark-models.yaml](file:///Users/moltisantid/Personal/experiments/experiments/jev-vs-llm/benchmark-models.yaml) with the following models:

| Registry Key | Model | Path in `~/.lmstudio/models/` |
|---|---|---|
| `qwen3.5-0.8b-q4km` | Qwen 3.5 0.8B (Q4_K_M) | `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q4_K_M.gguf` |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B (Q4_K_M) | `lmstudio-community/NVIDIA-Nemotron-3-Nano-4B-GGUF/NVIDIA-Nemotron-3-Nano-4B-Q4_K_M.gguf` |
| `nemotron-nano-4b-q8` | NVIDIA Nemotron-3-Nano-4B (Q8_0) | `lmstudio-community/NVIDIA-Nemotron-3-Nano-4B-GGUF/NVIDIA-Nemotron-3-Nano-4B-Q8_0.gguf` |
| `qwen3.5-9b-q4km` | Qwen 3.5 9B (Q4_K_M) | `lmstudio-community/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf` |

To use this configuration across runs:

```bash
# Option 1: Copy to ~/.local-llm/models.yaml (global default)
cp benchmark-models.yaml ~/.local-llm/models.yaml

# Option 2: Point Korgis to the benchmark file directly
export LOCAL_LLM_REGISTRY_PATHS="/Users/moltisantid/Personal/experiments/experiments/jev-vs-llm/benchmark-models.yaml"
```

Verify that Korgis resolves all 4 models:

```bash
cd /Users/moltisantid/Personal/experiments/korgis
uv run --frozen local-llm models
```

All 4 models should show as `✅ downloaded` with backend `llama_server`.

Start Korgis once with admin API enabled:

```bash
uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark can now evaluate each registered model directly or run the automated matrix.

---

## 6. Custom GGUF workflow C — add a download URL to Korgis

If you want Korgis to perform the download, define `filename` and `url` instead of `path`:

```yaml
models:
  my-model-4b-q4km:
    filename: "my-model-4b-Q4_K_M.gguf"
    url: "https://huggingface.co/<ORG>/<GGUF_REPO>/resolve/<REVISION>/my-model-4b-Q4_K_M.gguf"
    model_id: "org/model-4b"
    quantization: "Q4_K_M"
    sha256: "<EXPECTED_SHA256>"
    size_gb: 2.5
    backend: llama_server
    thinking_mode: none
    params:
      ctx_size: 8192
      startup_timeout: 300
      max_concurrent_requests: 1
      default_temperature: 0.0
      enable_thinking: false
      show_thinking: false
    tags: [local-benchmark, custom, 4b]
```

Then:

```bash
uv run --frozen local-llm download my-model-4b-q4km
uv run --frozen local-llm verify-artifact my-model-4b-q4km
```

This reproduces the same workflow as a built-in Korgis model without requiring a Korgis source-code change.

---

## 7. Experiment-specific external registry

Instead of modifying `~/.local-llm/models.yaml`, point Korgis at a dedicated registry file:

```bash
export LOCAL_LLM_REGISTRY_PATHS="/absolute/path/benchmark-models.yaml"
```

Then every Korgis command in that shell sees the extra entries:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm download my-model-4b-q4km
uv run --frozen local-llm serve \
  --model my-model-4b-q4km \
  --enable-admin-api \
  --no-download
```

Registry precedence is:

```text
built-in Korgis registry
        ↓
external registry files
        ↓
~/.local-llm/models.yaml
```

Use this mode when the registry configuration belongs to the experiment rather than to your machine globally.

---

## 8. Start Korgis for the managed benchmark

Once every desired model has a stable registry key and local artifact:

```bash
cd ~/dev/korgis

uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

Korgis exposes:

```text
http://127.0.0.1:1235/v1
```

In the benchmark shell:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export KORGIS_API_KEY="local"
```

The benchmark control plane can then activate each registered model sequentially.

This avoids keeping all GGUF weights resident at once.

---

## 9. Run one local model

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

For a custom registered model:

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model my-model-4b-q4km
```

---

## 10. Local-only benchmark

This runs no paid Jev or OpenAI inference:

```bash
uv run jev-bench compare-local --profile budget
```

Default matrix:

```text
Qwen3.5-4B Q4_K_M
MiniCPM3-4B Q4_K_M
Nemotron-3-Nano-4B Q4_K_M
Qwen3.5-9B Q4_K_M
```

Output:

```text
results/local_report.html
results/raw/local_results.csv
results/manifests/<run-group>.json
```

For a custom matrix (such as the LM Studio models):

```bash
uv run jev-bench compare-local \
  --profile budget \
  --models qwen3.5-0.8b-q4km,nemotron-nano-4b,nemotron-nano-4b-q8,qwen3.5-9b-q4km
```

Every key passed to `--models` must be resolvable by the Korgis server currently running. Korgis's admin API will automatically activate and swap each model in memory sequentially.

---

## 11. Combined cloud + local benchmark

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-local \
  --local-models qwen3.5-4b-q4km,minicpm3-4b-q4km,nemotron-nano-4b,qwen3.5-9b-q4km
```

Every system receives the same labelled cases in the same run group.

---

## 12. Fairness rules

- Local and GPT generative baselines receive the same bounded decision semantics.
- Local benchmark requests explicitly disable thinking/reasoning output where the runtime supports disabling it.
- GPT decision runs default to `OPENAI_REASONING_EFFORT=none`.
- Korgis requests use `response_format=json_object`; the benchmark validates allowed choices itself.
- Invalid JSON, missing answers and out-of-domain choices remain invalid outputs rather than being repaired.
- Temperature/sampling behavior is runtime configuration and is captured through Korgis identity where available.
- Client-observed latency includes the local HTTP boundary but excludes model startup/load time.
- Model switching is outside per-request inference latency.
- The run manifest snapshots Korgis `local-llm-identity-v1` identity for tested runtimes.
- For manually supplied GGUFs, record the authoritative source, revision, filename, quantization and SHA-256.

---

## 13. What to compare

The UI treats local models as first-class series alongside Jev and GPTs.

The most useful comparisons are:

1. valid-output rate;
2. routing accuracy and macro-F1;
3. calibration and OOS rejection;
4. 1→32 structured-output scaling;
5. workflow/agent reliability;
6. p50/p95/p99 latency;
7. token usage;
8. provider API cost.

Local models should normally appear at API cost zero. Interpret that as **provider fee**, not full economic cost.

---

## 14. Why MiniCPM3-4B is included

MiniCPM3-4B gives the benchmark another text-only architecture in approximately the same parameter/quantization tier as Qwen3.5-4B and Nemotron Nano 4B.

```text
Qwen3.5 4B       ┐
MiniCPM3 4B      ├─ model-family comparison at ~4B
Nemotron Nano 4B ┘

Qwen3.5 4B → Qwen3.5 9B
              └─ within-family size-scaling reference
```

MiniCPM-V is intentionally excluded because this benchmark evaluates text-only bounded decisions.

---

## 15. Autonomous Multi-Model Runner (`run_local_matrix.py`)

An autonomous orchestrator script is provided in [`scripts/run_local_matrix.py`](file:///Users/moltisantid/Personal/experiments/experiments/jev-vs-llm/scripts/run_local_matrix.py) to manage and evaluate multiple local models **sequentially, one at a time**, without requiring manual server restarts or terminal management.

### Key Features
- **Automatic Korgis Management**: Starts Korgis in the background if not already running, waits for health checks, and cleanly shuts it down when finished.
- **Sequential Memory Isolation**: Activates each model via the Korgis Admin API, executes the benchmarks, and immediately unloads it to completely free VRAM/RAM before loading the next model.
- **Live Progress Bar & Verbose Output**: Displays real-time per-case outcomes (predicted vs expected intent, latency, checkmark status), running accuracy percentage, elapsed time, and ETA.
- **Flexible Model Selection**: Pass models via command-line arguments, select them from an interactive menu, or define them in [`experiments_config.yaml`](file:///Users/moltisantid/Personal/experiments/experiments/jev-vs-llm/experiments_config.yaml).
- **Consolidated Summary & Dashboard**: Collects metrics across all evaluated models, appends results to `results/raw/local_results.csv`, and renders the interactive HTML report at `results/local_report.html`.


### Usage Examples

```bash
cd /Users/moltisantid/Personal/experiments/experiments/jev-vs-llm

# 1. List available configured models
uv run python scripts/run_local_matrix.py --list

# 2. Interactive selection (select numbers or 'a' for all)
uv run python scripts/run_local_matrix.py -i

# 3. Run ALL experiments on a selected model (Smoke Tier: fast ~1-2 min)
# Runs: 01-routing, 02-calibration, 03-scaling, 04-workflow, 05-hybrid-agent
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments all \
  --dataset smoke

# 4. Run ALL experiments on a selected model (Public Benchmark Tier: real Banking77 + CLINC150)
# Runs: 01-routing-public (77 banking classes) + 02-calibration-public (in-scope + out-of-scope)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments all \
  --dataset public \
  --profile budget

# 5. Run a single specific experiment on a selected model (e.g. routing)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments routing \
  --dataset public \
  --profile budget

# 6. Run a comma-separated subset of experiments on a selected model
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments routing,calibration \
  --dataset smoke

# 7. Run ALL models sequentially across ALL experiments
uv run python scripts/run_local_matrix.py \
  --models all \
  --experiments all \
  --dataset smoke

# 8. Keep Korgis running after benchmarks finish (optional, avoids restart on next run)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --keep-korgis
```

### Experiments Overview

| Experiment ID | Key | What it evaluates | Smoke Tier | Public Tier (`--dataset public`) |
|---|---|---|---|---|
| **01** | `routing` | Multi-class intent classification | 24 synthetic cases | 77 real BANKING77 intents (1 per class on `budget`) |
| **02** | `calibration` | Probability calibration & OOS rejection | 24 synthetic cases | BANKING77 in-scope + CLINC150 out-of-scope |
| **03** | `scaling` | 1 → 32 parallel decisions in a single call | 1, 2, 4, 8, 16, 32 questions | Smoke only |
| **04** | `workflow` | Deterministic policy (model decisions + Python rules) | Support ticket routing rules | Smoke only |
| **05** | `agent` | Hybrid agent decision layer & escalation | Expense approval workflow | Smoke only |

> [!TIP]
> When using `--experiments all`:
> - With `--dataset smoke`: runs all 5 experiments (`routing`, `calibration`, `scaling`, `workflow`, `agent`).
> - With `--dataset public`: runs the 2 public benchmark experiments (`routing` and `calibration`).

### Configuration (`experiments_config.yaml`)

Default runner parameters can be adjusted in [`experiments_config.yaml`](file:///Users/moltisantid/Personal/experiments/experiments/jev-vs-llm/experiments_config.yaml):

```yaml
korgis_dir: "/Users/moltisantid/Personal/experiments/korgis"
korgis_port: 1235
default_models:
  - "qwen3.5-0.8b-q4km"
  - "nemotron-nano-4b"
  - "nemotron-nano-4b-q8"
  - "qwen3.5-9b-q4km"
default_experiments:
  - "routing"
dataset: "smoke"
public_profile: "budget"
max_output_tokens: 512
stop_korgis_on_complete: true
```

### Note on Reasoning Models (e.g. Qwen) and Structured Outputs

Models with built-in reasoning templates (like Qwen) emit `<think>...</think>` tags by default. In `llama-server`, thinking tokens are segregated into `reasoning_content` and do not have JSON schema constraints applied. In long multi-class prompts (like BANKING77 with 77 classes), this can exhaust `max_output_tokens` before reaching the JSON block, returning empty content and a `502 invalid_model_output`.

The orchestrator automatically sets `LLAMA_ARG_REASONING=off` by default to disable thinking traces during structured benchmark tasks, ensuring prompt GBNF grammar constraints and direct fast JSON responses.



