# Korgis local-model comparison

The Jev-vs-LLM suite can run the same public decision benchmark through Korgis / Local LLM Server.

## Local matrix

| Korgis registry key | Model | Quantization | Provider API fee |
|---|---|---|---:|
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | $0 |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | $0 |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | $0 |

Qwen3.5 has official 4B and 9B checkpoints, not an official 8B checkpoint. The 9B model is therefore used as the larger Qwen3.5 comparison.

A zero provider API fee is **not** a zero total-cost-of-ownership claim. Electricity, hardware purchase/amortisation, thermal impact and opportunity cost of the device are outside the current cost model.

## Korgis prerequisite

Use a Korgis revision that contains the three registry entries. Download the GGUF files first:

```bash
local-llm download qwen3.5-4b-q4km
local-llm download qwen3.5-9b-q4km
local-llm download nemotron-nano-4b
```

For the default memory-bounded managed mode, start Korgis with the small Nemotron anchor and the admin API:

```bash
local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark then uses the Korgis control plane to activate each Qwen runtime sequentially, returns to the Nemotron anchor, and unloads the temporary runtime. This avoids keeping all three GGUF weights resident at once.

## Local-only benchmark

This runs no paid Jev or OpenAI inference:

```bash
uv run jev-bench compare-local --profile budget
```

Default matrix:

```text
Qwen3.5-4B Q4_K_M
Qwen3.5-9B Q4_K_M
Nemotron-3-Nano-4B Q4_K_M
```

Output:

```text
results/local_report.html
results/raw/local_results.csv
results/manifests/<run-group>.json
```

## Combined cloud + local benchmark

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-local \
  --local-models qwen3.5-4b-q4km,qwen3.5-9b-q4km,nemotron-nano-4b
```

Every system receives the same labelled cases in the same run group.

## Fairness rules

- Local and GPT generative baselines are asked for the same bounded decision representation.
- Local benchmark requests explicitly disable thinking/reasoning output.
- GPT decision runs default to `OPENAI_REASONING_EFFORT=none`.
- Korgis requests use `response_format=json_object`, and the benchmark validates allowed choices itself.
- Invalid JSON, missing answers and out-of-domain choices count as invalid outputs rather than being repaired.
- Temperature/sampling behavior is model/runtime configuration and is recorded through Korgis runtime identity.
- Client-observed latency includes the local HTTP boundary but excludes model startup/load time. Model switching is outside per-request latency.
- The run manifest snapshots Korgis `local-llm-identity-v1` identity for each tested runtime.

## What to compare

The UI treats local models as first-class series alongside Jev and GPTs. The most useful comparisons are:

1. accuracy vs latency;
2. accuracy vs provider API cost;
3. 77-way routing accuracy and macro-F1;
4. calibration and OOS rejection;
5. invalid-output rate.

Local models should usually appear at API cost zero. Interpret that axis as **provider fee**, not full economic cost.
