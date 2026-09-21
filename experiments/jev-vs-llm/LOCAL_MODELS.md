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

Registry-managed download example:

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
