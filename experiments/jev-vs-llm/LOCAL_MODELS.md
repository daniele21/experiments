# Local model setup for the Jev benchmark

This document covers only **models executed locally through Korgis**.

MiniCPM is deliberately not configured here. The benchmark calls MiniCPM through the official ModelBest API with an API key; see [`MINICPM_API.md`](MINICPM_API.md).

## 1. Local matrix

The default matrix is restricted to model keys that exist in the current Korgis built-in registry.

| Korgis key | Model | Runtime / quantization | Provider API fee |
|---|---|---|---:|
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | llama-server / Q4_K_M GGUF | $0 |
| `qwen3-vl-4b` | Qwen3-VL-4B-Instruct | MLX VLM server / 4-bit | $0 |

This is intentional. A benchmark default must work from a clean Korgis installation; it must not contain guessed or undocumented registry keys.

The local provider fee is recorded as zero. Hardware purchase/amortisation, electricity, thermal impact and device opportunity cost are outside the current cost model.

## 2. Install Korgis

A convenient layout is:

```text
~/dev/
├── experiments/
└── korgis/
```

Clone and prepare Korgis:

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

## 3. Install llama-server for GGUF models

The `nemotron-nano-4b` entry uses Korgis' `llama_server` backend.

On macOS/Linux with Homebrew:

```bash
brew install llama.cpp
command -v llama-server
llama-server --version
```

Optionally pin the executable:

```bash
export LOCAL_LLM_SERVER_BIN="$(command -v llama-server)"
```

The three layers are distinct:

```text
Korgis                    control plane / lifecycle / HTTP API
llama-server              GGUF inference runtime
model artifact            weights
```

## 4. Trust the registry, not guessed model names

Always inspect the active merged registry first:

> [!TIP]
> Korgis listens on port `1235` by default (as configured in `.env`). If another process is holding the port, identify and terminate it:
> ```bash
> lsof -i :1235
> kill <PID>
> ```

The commands below use `uv run --frozen local-llm` so they always execute the Korgis environment from this checkout.

```bash
cd ~/dev/korgis
uv run --frozen local-llm models
```

The built-in benchmark keys should include:

```text
nemotron-nano-4b
qwen3-vl-4b
```

A command such as:

```bash
local-llm download some-name
```

works only if `some-name` resolves to a real registry entry containing the source/backend information Korgis needs.

Do not infer a key from a model family or quantization name.

## 5. Download and verify the GGUF baseline

For the built-in Nemotron GGUF:

```bash
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm verify-artifact nemotron-nano-4b
```

The registry pins the artifact source and metadata used by Korgis.

For evidence-quality benchmark runs, retain the runtime identity and artifact verification information in the run manifest.

## 6. Start Korgis

Start with the anchor/default GGUF model:

```bash
cd ~/dev/korgis

uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark defaults to:

```text
http://127.0.0.1:1235/v1
```

Set:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export KORGIS_API_KEY="local"
export KORGIS_MODELS="nemotron-nano-4b,qwen3-vl-4b"
```

Check the server:

```bash
curl http://127.0.0.1:1235/health
curl http://127.0.0.1:1235/v1/models
curl http://127.0.0.1:1235/v1/runtime/identity
```

## 7. Run one local benchmark

From the benchmark checkout:

```bash
cd ~/dev/experiments/experiments/jev-vs-llm

uv run jev-bench experiment routing \
  --provider korgis \
  --model nemotron-nano-4b
```

Public BANKING77 routing:

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model nemotron-nano-4b \
  --dataset public \
  --profile budget
```

## 8. Run the local matrix

```bash
uv run jev-bench compare-local --profile budget
```

Or choose the keys explicitly:

```bash
uv run jev-bench compare-local \
  --profile budget \
  --models nemotron-nano-4b,qwen3-vl-4b
```

Korgis' admin API activates models sequentially and captures runtime identity. The benchmark does not require every model to remain resident at once.

## 9. Add a local model that Korgis does not ship

There are two supported patterns.

### 9.1 One-off local artifact

If you already have a compatible GGUF:

```bash
uv run --frozen local-llm serve \
  --model my-local-model \
  --model-path "$HOME/models/my-model-Q4_K_M.gguf" \
  --backend llama_server \
  --ctx-size 8192 \
  --enable-admin-api \
  --no-download
```

This is useful for a smoke test, but it is not the preferred path for a reproducible multi-model benchmark.

### 9.2 Stable user/external registry entry

Create `~/.local-llm/models.yaml` or use an experiment-specific registry via `LOCAL_LLM_REGISTRY_PATHS`.

Local path example:

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
    tags: [local-benchmark, custom]
```

### 9.3 LM Studio Local Models (Ready-to-use Registry Configuration)

If you have downloaded GGUF models via LM Studio (typically residing under `~/.lmstudio/models/`), you can register them cleanly. This repository includes a pre-configured registry file [`benchmark-models.yaml`](benchmark-models.yaml) with the following models:

| Registry Key | Model | Path in `~/.lmstudio/models/` |
|---|---|---|
| `qwen3.5-0.8b-q4km` | Qwen 3.5 0.8B (Q4_K_M) | `unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q4_K_M.gguf` |
| `qwen3.5-2b-q4km` | Qwen 3.5 2B (Q4_K_M) | `unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf` |
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

Verify that Korgis resolves all configured models:

```bash
cd /Users/moltisantid/Personal/experiments/korgis
uv run --frozen local-llm models
```

All configured models should show as `✅ downloaded` with backend `llama_server`.

Start Korgis once with admin API enabled:

```bash
uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark can now evaluate each registered model directly or run the automated matrix.

### 9.4 Registry-managed download example

```yaml
models:
  my-model-4b-q4km:
    filename: "my-model-4b-Q4_K_M.gguf"
    url: "https://huggingface.co/<ORG>/<REPO>/resolve/<REVISION>/<FILE>.gguf"
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
    tags: [local-benchmark, custom]
```

Then:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm download my-model-4b-q4km
uv run --frozen local-llm verify-artifact my-model-4b-q4km
```

For an experiment-owned registry:

```bash
export LOCAL_LLM_REGISTRY_PATHS="/absolute/path/benchmark-models.yaml"
uv run --frozen local-llm models
```

## 10. Reproducibility rules

For every local model used as benchmark evidence, record:

- Korgis registry key;
- canonical model ID;
- backend;
- quantization;
- source URL or local artifact path;
- immutable source revision when available;
- SHA-256 for downloaded artifacts when available;
- Korgis runtime identity;
- machine/OS and benchmark location.

Do not silently rename a model, swap quantizations or replace one artifact with another under the same benchmark label.

## 11. MiniCPM is not a local default

The old benchmark configuration treated `minicpm3-4b-q4km` as though it were a real Korgis model key. It is not part of the Korgis built-in registry and must not be presented as a default downloadable model.

The benchmark now treats MiniCPM as a separate remote provider:

```text
jev-bench
   ↓
OpenAI-compatible MiniCPM API
   ↓
https://api.modelbest.cn/v1
```

Use [`MINICPM_API.md`](MINICPM_API.md) for its setup.

If a future experiment deliberately self-hosts a MiniCPM artifact, add that artifact to a reproducible Korgis registry entry and label it as a separate local experiment. Do not conflate it with the official API baseline.

---

## 12. Autonomous Multi-Model Runner (`run_local_matrix.py`)

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
  - "qwen3.5-2b-q4km"
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
