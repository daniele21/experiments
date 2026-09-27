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

## BANKING77

Run the exact same public routing harness used by the other providers:

```bash
uv run jev-bench prepare-data

uv run jev-bench experiment routing \
  --provider clm \
  --dataset public \
  --profile standard
```

For an exploratory 77-case pass use `--profile budget`. For publication-grade
evidence prefer `standard` or `full`, pin the CLM checkpoint/model identity,
record the runner location, and run every directly compared system against the
same profile and seed.

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
