# Portfolio evidence publication — Jev vs LLM

This directory is a **curated public export**, not the complete benchmark database.

## What is currently published

- Routing: five local-Korgis model aggregates (332 total model-requests).
- Four rows contain 77 requests each; one has 24.
- Calibration, parallel scaling, deterministic workflow and hybrid agent: **no published numerical results**.
- No Jev/TypeSafe/CLM performance numbers or raw prompts/cases are included.
- **No direct Jev-vs-LLM result is available in this snapshot.**

The same number of requests does **not** establish that the underlying cases, prompts, configurations and runtime conditions are identical. This is a descriptive model-baseline summary, **not** an authorized Jev-versus-LLM verdict.

## Source & provenance

The current `portfolio-summary.json` projects the local Korgis data already versioned in source commit
`5d0563b0624fd476ed9b07137bb873408869d700`,
at `experiments/jev-vs-llm/results/benchmark_data.json`.
The JSON itself records the source, provider coverage and unpublished experiment types.

## Regenerate (standard-library Python only)

From the repository root:

```bash
git fetch origin feature/clm-autonomous-runner
git show 5d0563b0624fd476ed9b07137bb873408869d700:experiments/jev-vs-llm/results/benchmark_data.json > /tmp/jev-source.json

cd experiments/jev-vs-llm
python3 scripts/publish_portfolio_summary.py \
  --input /tmp/jev-source.json \
  --source-ref 5d0563b0624fd476ed9b07137bb873408869d700 \
  --source-path experiments/jev-vs-llm/results/benchmark_data.json \
  --output results/published/portfolio-summary.json

python3 -m pytest tests/test_publish_portfolio_summary.py
```

To publish new evidence, build an authoritative benchmark JSON from measured runs, review publication rights and comparability, then invoke the public exporter on a **versioned input**. Never point the website at private runs or UI fixture JSON.

## Publication policy

The exporter **fails closed** without allowlisted aggregates. It allowlists providers and fields: raw case data, prompts, responses, metadata, and run identifiers are never copied.

Providers/model IDs linked to `jev`, `typesafe`, `clm`, or System One are excluded even when the source contains numerical results.

The project's README warns that TypeSafe's Master Customer Agreement may restrict publication of benchmark/performance information. Verified authorization and reviewed code changes are required before including those metrics. Do not bypass this exporter to paste restricted results into the portfolio.

The published schema lists five experiments but currently supplies numerical data only for Routing, with provider-level checks. Future experiment adapters require their own data provenance, permission reviews and comparability tests.
