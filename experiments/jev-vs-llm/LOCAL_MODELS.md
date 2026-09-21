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

Verify that Korgis now resolves the key:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm verify-artifact my-model-4b-q4km
```

Start it:

```bash
uv run --frozen local-llm serve \
  --model my-model-4b-q4km \
  --enable-admin-api \
  --no-download
```

The benchmark can now refer to the stable key:

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model my-model-4b-q4km
```

This is the preferred path for a manually downloaded GGUF that will participate in benchmark evidence.

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

For a custom matrix:

```bash
uv run jev-bench compare-local \
  --profile budget \
  --local-models qwen3.5-4b-q4km,my-model-4b-q4km,nemotron-nano-4b
```

Every key passed to `--local-models` must be resolvable by the Korgis server currently running.

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
