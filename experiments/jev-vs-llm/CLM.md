# CLM-8B benchmark provider

This benchmark can run the same typed decision cases against
[Contrastive-LM/CLM](https://github.com/Contrastive-LM/CLM), including the
BANKING77 public routing benchmark.

CLM is deliberately integrated through its official TypeSafe-compatible
`POST /v1/systemone` HTTP wire protocol. The benchmark does not import CLM
or manage its GPU lifecycle.

## Why this is a useful benchmark arm

BANKING77 is a bounded 77-way choice. CLM embeds the shared state and the
candidate action texts separately, then scores the candidates contrastively.
That makes it architecturally different from an autoregressive local LLM while
still fitting the same `DecisionProvider` contract used by the benchmark.

The 77 intent descriptions are reused across cases, so CLM's action-vector
cache is directly relevant. Keep cold-cache and warm-cache latency claims
separate when publishing results.

## Reference CLM-8B serving

The upstream reference implementation currently requires Python 3.10+, Linux
and an NVIDIA GPU for the vLLM Qwen3-8B pooling encoder.

On the GPU host:

```bash
git clone https://github.com/Contrastive-LM/CLM.git
cd CLM
pip install -r requirements.txt

vllm serve Qwen/Qwen3-8B \
  --served-model-name qwen3-8b \
  --runner pooling \
  --enable-prefix-caching \
  --max-model-len 2048 \
  --gpu-memory-utilization 0.35 \
  --port 8090

clm-serve \
  --port 8700 \
  --emb-url http://127.0.0.1:8090/v1/embeddings
```

For a remote GPU, expose the service only through a trusted network or SSH
tunnel. For example:

```bash
ssh -L 8700:localhost:8700 <gpu-host>
```

Then configure the benchmark runner:

```bash
export CLM_BASE_URL=http://127.0.0.1:8700
export CLM_MODEL=clm-latest
export CLM_TEMPERATURE=1.0
# export CLM_API_KEY=...   # only when the server requires it
```

## Managed local GGUF runtime: Q4_K_M-outq2

The repository also supports the quantized CLM encoder artifact
`czl/CLM-v0.1-8B-GGUF/Qwen3-8B-Q4_K_M-outq2.gguf` as a managed local
runtime.

This artifact is **not** a generative Korgis baseline. It is the Qwen3-8B
encoder used by CLM for last-token-pooled embeddings; `clm-serve` still owns
the CLM state/action projection heads and the `/v1/systemone` API. The
`output.weight` tensor is stored at Q2 in the `-outq2` variant because the
pooling path does not use the language-model output head. The benchmark
therefore records it as a CLM runtime identity rather than registering it as a
normal text-generation model.

The portable runtime contract is checked in as
[`clm_runtimes.yaml`](clm_runtimes.yaml). The machine-local GGUF path is kept
outside git:

```bash
export CLM_ENCODER_GGUF="/absolute/path/to/CLM-v0.1-8B-GGUF/Qwen3-8B-Q4_K_M-outq2.gguf"

# Required executables. Explicit env vars are optional when both are on PATH.
export CLM_LLAMA_SERVER_BIN="$(command -v llama-server)"
export CLM_SERVE_BIN="$(command -v clm-serve)"
```

Install the official CLM package separately if `clm-serve` is not available:

```bash
python -m pip install contrastive-lm
```

The first run may need network access so `clm-serve` can fetch the official
`Contrastive-LM/CLM-v0.1-8B` head. To use a pre-downloaded checkpoint instead:

```bash
export CLM_CKPT="/absolute/path/to/CLM_v0.1-8B.pt"
```

### One-command BANKING77 run

From `experiments/jev-vs-llm`:

```bash
uv run python scripts/run_clm_matrix.py \
  --runtime clm-v0.1-8b-q4km-outq2 \
  --experiments routing \
  --dataset public \
  --profile budget
```

The runner:

1. validates the exact registered GGUF filename;
2. starts `llama-server` in embeddings mode with last-token pooling;
3. waits for the OpenAI-compatible embeddings endpoint;
4. starts `clm-serve` against that endpoint;
5. validates CLM health and the served checkpoint;
6. runs the normal BANKING77 harness with per-case progress and ETA;
7. records `clm-v0.1-8b-q4km-outq2` in CSV/report rows while retaining
   `clm-latest` as the actual wire-protocol model in raw evidence;
8. stops only the processes it created.

Existing listeners are never killed. If ports 8090 or 8700 are already in use,
the managed runtime fails fast rather than replacing another process.

Use `--keep-runtime` to leave the two local services running after the run.
Logs are written under `results/logs/`.

### Unified comparison with Jev / GPT / Korgis

The same runtime can be launched by `compare-public`, which keeps all systems
inside one run group and one report:

```bash
export JEV_MODEL=jev-1.13.0
export CLM_ENCODER_GGUF="/absolute/path/to/CLM-v0.1-8B-GGUF/Qwen3-8B-Q4_K_M-outq2.gguf"

uv run jev-bench compare-public \
  --profile standard \
  --include-clm \
  --clm-runtime clm-v0.1-8b-q4km-outq2 \
  --include-local
```

Add `--no-include-openai` if the comparison should contain only Jev, CLM and
the selected local Korgis models. Use `--local-models ...` to constrain the
Korgis matrix.

The runtime registry intentionally separates:

```text
benchmark identity           clm-v0.1-8b-q4km-outq2
CLM served model             clm-latest
CLM head                     Contrastive-LM/CLM-v0.1-8B
encoder                      czl/CLM-v0.1-8B-GGUF
encoder artifact             Qwen3-8B-Q4_K_M-outq2.gguf
pooling                      last
```

This prevents a quantized encoder run from being reported ambiguously as just
`clm-latest`.

## BANKING77

The recommended entry point is the autonomous runner used by
[`RUN_EXPERIMENTS.md`](RUN_EXPERIMENTS.md). It performs CLM health/model
preflight, prepares the public data, prints per-case progress, writes cumulative
raw rows, records one manifest and builds the HTML report.

The first 77-case BANKING77 pass is simply:

```bash
uv run python scripts/run_clm_matrix.py
```

Equivalent explicit form:

```bash
uv run python scripts/run_clm_matrix.py \
  --models clm-latest \
  --experiments routing \
  --dataset public \
  --profile budget
```

For the 770-case standard profile:

```bash
uv run python scripts/run_clm_matrix.py \
  --models clm-latest \
  --experiments routing \
  --dataset public \
  --profile standard
```

The lower-level single-experiment CLI remains available:

```bash
uv run jev-bench experiment routing \
  --provider clm \
  --dataset public \
  --profile standard
```

For publication-grade evidence prefer `standard` or `full`, pin the CLM
checkpoint/model identity, record the runner location, and run every directly
compared system against the same profile and seed.

## Combined public comparison

`compare-public --include-clm` adds CLM to the same run group and report:

```bash
uv run jev-bench compare-public \
  --profile standard \
  --no-include-openai \
  --include-clm
```

Add `--include-local` to include the configured Korgis local matrix as well.

## Cost and latency semantics

- `estimated_cost_usd=0` means zero provider API fee for the self-hosted CLM
  endpoint. Hardware, energy and GPU amortisation are not measured.
- `latency_ms` is client-observed end-to-end latency.
- The raw provider payload also records the upstream `X-CLM-Latency-Ms`
  server timing when present.
- CLM does not expose cached-input tokens through the System One response, so
  `cached_input_tokens` is left unknown rather than set to zero.
- Do not mix the first cold-cache request with warm-cache claims. The action
  cache can reuse the BANKING77 candidate embeddings across subsequent cases.
