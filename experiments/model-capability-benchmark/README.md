# Model Capability Benchmark

A reusable benchmark suite for comparing local and API-hosted models across multiple
capabilities, datasets and evaluators.

The suite is being built on top of the shared `benchmark-core` package extracted from
`jev-vs-llm`.

## Current status

- MCB-0 baseline: complete;
- MCB-1 generic contracts: complete;
- MCB-2 benchmark-core extraction: complete;
- MCB-3 unified model/runtime/provider registry: complete;
- MCB-4 task plugin registry: complete;
- MCB-5 dataset registry/adapters: complete;
- MCB-6 five-capability suite: complete;
- MCB-7 unified matrix runner: implemented and CI-covered; controlled real Korgis + API validation pending;
- MCB-8 neutral capability reporting: complete;
- MCB-9 Jev consolidation/migration: complete.

## Registry

The first operational configuration is `models.yaml`.

The registry deliberately separates three identities:

```text
ModelSpec
   ↓ runtime
RuntimeSpec
   ↓ provider
ProviderSpec
```

A model can therefore move between runtimes without redefining task or dataset logic. The same registry also carries the shared multimodal capability flags used by the VLM and image-generation tracks.

For local models, `model_id` is the canonical model identity while
`runtime_model_id` is the alias exposed by the serving runtime.

Example:

```text
model_key:        qwen3.5-2b-q4km
model_id:         unsloth/qwen3.5-2b
runtime_model_id: qwen3.5-2b-q4km
runtime:          korgis-local
deployment:       local
```

No credentials or machine-specific filesystem paths belong in this registry.

## Inspect the registry

From `experiments/jev-vs-llm`, where the current locked development environment already
installs `benchmark-core`:

```bash
uv run --frozen python ../model-capability-benchmark/scripts/registry_inspect.py
```

Select specific models:

```bash
uv run --frozen python ../model-capability-benchmark/scripts/registry_inspect.py \
  --models qwen3.5-2b-q4km,gpt-5.6-luna
```

Filter declaratively:

```bash
uv run --frozen python ../model-capability-benchmark/scripts/registry_inspect.py \
  --models all \
  --deployment local \
  --tag open-weight \
  --max-parameters-b 4 \
  --quantization Q4_K_M
```

## Preflight

Preflight checks only dependencies needed by the selected models.

For a local Korgis model:

```bash
export KORGIS_BASE_URL=http://127.0.0.1:1235/v1

uv run --frozen python ../model-capability-benchmark/scripts/registry_inspect.py \
  --models qwen3.5-2b-q4km \
  --preflight
```

For an OpenAI API model, `OPENAI_API_KEY` must be present before execution. The key is
read from the environment and is never written to the registry or manifest.

See `.env.example` for the currently supported environment variables.

## Capability suite

`suite.yaml` now composes five capability families: BANKING77 intent classification,
BANKING77 + CLINC150 OOS/top-label calibration, structured output with real JSON Schema
validation, QA with abstention, and final-answer-only mathematical reasoning.

Inspect the same suite across a local and API model without provider calls:

```bash
uv run python scripts/suite_inspect.py \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities all
```

## Unified runner

The `model-bench` CLI now executes the same capability matrix across local and API
models:

```bash
uv run model-bench run \
  --run-group capability-smoke \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities structured-output,mathematical-reasoning \
  --profile smoke
```

The runner persists `state.jsonl`, `raw.jsonl`, `evaluation.jsonl`,
`aggregates.jsonl`, `report_index.jsonl`, `events.jsonl`,
`environment.json` and `run_manifest.json` incrementally.

Re-running the same semantic matrix resumes from completed case identities. Use
`--retry-failures` to rerun only terminal failed cases.

Korgis model residency is managed through its admin API; the Korgis server process itself
is intentionally external to this benchmark.

See `MCB_7_UNIFIED_RUNNER.md` for architecture, failure semantics and the controlled
real-provider validation runbook.

## Capability report

Every run now produces a neutral capability × model report without an overall score or
winner ranking:

```text
report.html
report.json
```

The HTML includes the declared primary metric for each capability, secondary metrics,
model/runtime metadata, exact case-attempt drill-down and infrastructure events.

A persisted run can be rendered again without provider credentials or a running runtime:

```bash
uv run model-bench report \
  --run-dir results/runs/capability-smoke
```

Unknown provider cost remains `null`; a local provider fee of zero is not interpreted as
zero hardware/runtime cost.

See `MCB_8_REPORTING.md` for the evidence/report contract.

## What comes next

The MCB-0…9 architecture workstream is complete. The next validation step is the controlled
real-provider E2E documented in `MCB_7_UNIFIED_RUNNER.md`: run the same capability slice
through Korgis and an API model, then inspect the persisted evidence and neutral report.

Jev remains a bounded-decision suite on top of the same core. Its task semantics and rich
Jev-specific dashboard stay intentionally separate from the generic capability report.
