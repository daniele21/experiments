# Korgis local model setup

## Required Korgis revision

This experiment targets the recent Korgis `dev` revision:

```text
26a161dc0ef89a133c7a076d3a31544a274c1469
```

That revision adds built-in, reproducible Qwen3.5 Q4_K_M registry entries and pins SHA-256 metadata for the Qwen artifacts.

The benchmark intentionally does not ship its own model registry for these four defaults. Model acquisition and runtime metadata belong to Korgis.

## Download

From the pinned Korgis checkout:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm download nemotron-nano-4b-q8
uv run --frozen local-llm download qwen3.5-4b-q4km
uv run --frozen local-llm download qwen3.5-9b-q4km
```

For evidence-quality runs, verify artifacts when Korgis has verification metadata:

```bash
uv run --frozen local-llm verify-artifact qwen3.5-4b-q4km
uv run --frozen local-llm verify-artifact qwen3.5-9b-q4km
```

## Start

```bash
uv run --frozen local-llm serve   --model nemotron-nano-4b   --enable-admin-api   --no-download
```

The benchmark uses:

```text
GET  /health
GET  /v1/runtime/identity
GET  /api/v1/models/registry
POST /api/v1/models/activate
POST /v1/chat/completions
```

Default base URL:

```text
http://127.0.0.1:1235/v1
```

## Fairness

All benchmark requests use:

```text
temperature = 0
enable_thinking = false
show_thinking = false
```

The comparison is intended to measure bounded PII extraction rather than chain-of-thought/reasoning generation.

## Adding future models

Prefer adding a stable model to Korgis when it is broadly useful across products/experiments. Use an experiment-owned external registry only for genuinely experimental artifacts.

Never put a guessed model key in the benchmarkn. A model is runnable only if the active Korgis registry can resolve its artifact/backend configuration.
