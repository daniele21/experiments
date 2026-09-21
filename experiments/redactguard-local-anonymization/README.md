# RedactGuard local anonymization benchmark

Reproducible benchmark for measuring how local models perform as the **PII detection engine of RedactGuard** when served by **Korgis**.

The benchmark does not embed Korgis and does not start a private inference engine. Korgis is an external local service reached only through its current public HTTP/control-plane contracts.

## What this experiment answers

> Which local model / quantization gives RedactGuard the best privacy-quality-latency trade-off?

Primary metrics are intentionally privacy-oriented:

- PII recall;
- character leakage rate;
- zero-leak document rate;
- precision and over-redaction;
- valid JSON rate;
- p50 / p95 / p99 client-observed inference latency.

The primary scoring unit is the **final RedactGuard span set after deterministic post-processing**, not merely the model's raw JSON.

## Compatibility baseline

This v0.1 is pinned to:

- frozen RedactGuard detection contract source: `daniele21/redact-guard@70ea5ed4fbbd7182010cc04eb756f636791c5947`;
- current RedactGuard Korgis integration baseline: `daniele21/redact-guard@b5ac4377b2947ccb954369c3df7cce1e13994df8` (`main`);
- Korgis recent development baseline: `daniele21/korgis@26a161dc0ef89a133c7a076d3a31544a274c1469` (`dev`);
- Korgis identity protocol: `local-llm-identity-v1`;
- inference API: `POST /v1/chat/completions`;
- lifecycle API: `/api/v1/models/activate`;
- reproducibility evidence: `GET /v1/runtime/identity`.

Korgis `dev` is deliberate here: that revision contains the recent Qwen3.5 Q4_K_M registry additions used by this benchmark. Do not silently run an older Korgis checkout and publish the results as comparable evidence.

## Initial local model matrix

All four keys are present in the pinned Korgis registry:

| Key | Model | Quantization | Purpose |
|---|---|---|---|
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | RedactGuard-size baseline |
| `nemotron-nano-4b-q8` | NVIDIA Nemotron-3-Nano-4B | Q8_0 | quantization comparison |
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | same-size model comparison |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | larger-local reference |

## Setup

Clone Korgis next to this repository and check out the tested revision:

```bash
git clone https://github.com/daniele21/korgis.git
cd korgis
git checkout 26a161dc0ef89a133c7a076d3a31544a274c1469

python3 -m pip install "uv==0.8.13"
uv sync --frozen --extra dev
```

Install `llama-server` if it is not already available:

```bash
brew install llama.cpp
command -v llama-server
```

Download the model artifacts through **Korgis itself**:

```bash
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm download nemotron-nano-4b-q8
uv run --frozen local-llm download qwen3.5-4b-q4km
uv run --frozen local-llm download qwen3.5-9b-q4km
```

Start only an anchor model; the benchmark activates the requested models sequentially:

```bash
uv run --frozen local-llm serve   --model nemotron-nano-4b   --enable-admin-api   --no-download
```

In a second terminal:

```bash
cd experiments/redactguard-local-anonymization
uv sync --extra dev
uv run redact-bench check-korgis
uv run redact-bench check-data
```

## Run the comparison

```bash
uv run redact-bench compare
```

For benchmark-grade repeated latency evidence:

```bash
uv run redact-bench latency --warmups 5 --repeats 30
```

Or select a smaller matrix:

```bash
uv run redact-bench compare   --models nemotron-nano-4b,qwen3.5-4b-q4km
```

Each run creates:

```text
results/<run-id>/
├── manifest.json
├── metrics.json
├── rows.json
├── <model>.jsonl
└── report.html
```

The manifest captures the exact Korgis runtime identity for every activated model.

## What is copied from RedactGuard

The experiment freezes only the behavior needed to make results reproducible:

1. built-in PII profile taxonomy, descriptions and examples;
2. RedactGuard system-prompt contract;
3. value-to-source-span post-processing semantics.

It does **not** depend on the RedactGuard Python package at runtime and does not import Korgis code. This keeps both product repositories independently evolvable while making benchmark drift explicit.

## Current dataset scope

`data/smoke/cases.jsonl` is a small deterministic integration dataset spanning General, Healthcare, Financial and Legal profiles. It is for harness validation, not for publishing model-quality conclusions.

The next benchmark tier should add an externally labelled generic PII dataset plus a RedactGuard-specific domain set. See [DATASETS.md](DATASETS.md).

## Boundary with the RedactGuard product

RedactGuard `main` now uses Korgis as the external local runtime boundary and no longer owns an embedded `llama_cpp_server.py`, GGUF downloader, or private model lifecycle. The product integration baseline is `b5ac4377b2947ccb954369c3df7cce1e13994df8`.

The benchmark deliberately keeps the earlier RedactGuard detection-contract SHA frozen because the migration changed runtime plumbing, not the benchmarked prompt/taxonomy/value-to-span semantics. This preserves reproducibility while keeping the product and experiment on the same Korgis architecture.
