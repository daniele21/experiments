# Korgis local-model comparison

The Jev-vs-LLM suite can run the same public decision benchmark through Korgis / Local LLM Server.

## Local matrix

| Korgis registry key | Model | Quantization | Provider API fee |
|---|---|---|---:|
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | $0 |
| `minicpm3-4b-q4km` | MiniCPM3-4B | Q4_K_M | $0 |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | $0 |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | $0 |

The matrix intentionally contains three roughly 4B-class models — Qwen3.5-4B, MiniCPM3-4B and Nemotron Nano 4B — plus Qwen3.5-9B as a larger reference. MiniCPM3-4B uses the official OpenBMB GGUF Q4_K_M artifact (~2.47 GB), pinned by SHA-256 in the Korgis registry. Qwen3.5 has official 4B and 9B checkpoints, not an official 8B checkpoint.

A zero provider API fee is **not** a zero total-cost-of-ownership claim. Electricity, hardware purchase/amortisation, thermal impact and opportunity cost of the device are outside the current cost model.

## Korgis prerequisite

Use a Korgis revision that contains the four benchmark registry entries. Download the GGUF files first:

```bash
local-llm download qwen3.5-4b-q4km
local-llm download minicpm3-4b-q4km
local-llm download nemotron-nano-4b
local-llm download qwen3.5-9b-q4km
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

## Combined cloud + local benchmark

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-local \
  --local-models qwen3.5-4b-q4km,minicpm3-4b-q4km,nemotron-nano-4b,qwen3.5-9b-q4km
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


## Why MiniCPM3-4B is included

MiniCPM3-4B is useful because it gives the benchmark another text-only architecture in approximately the same parameter/quantization tier as Qwen3.5-4B and Nemotron Nano 4B.

That enables a cleaner comparison:

```text
Qwen3.5 4B      ┐
MiniCPM3 4B     ├─ architecture/model-family comparison at ~4B
Nemotron Nano 4B┘

Qwen3.5 4B → Qwen3.5 9B
              └─ within-family size scaling reference
```

The benchmark uses the official `openbmb/MiniCPM3-4B-GGUF` Q4_K_M artifact, not MiniCPM-V. The multimodal MiniCPM-V family is intentionally excluded because this benchmark evaluates text-only bounded decisions.
