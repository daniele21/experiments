# Model Capability Benchmark

For day-to-day execution, start with **[HOW_TO_USE.md](HOW_TO_USE.md)**. It describes the recommended model-by-model flow: preflight → estimate → scratch smoke → canonical core verticals → projection → comparison → share rendering.

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
- MCB-9 Jev consolidation/migration: complete;
- MCB-10 vertical benchmark hardening: implemented on the v2 task-vertical suite and covered by consolidation gates; controlled real-provider validation remains an operational gate;
- MCB-11 observability/results explorer: core complete with immutable evidence, deterministic projection, multi-capability analysis, model/run history, disagreement explorer, Compare UI and a dedicated Python/frontend CI gate;
- MCB-12 efficiency telemetry/share renderer: core complete with Korgis CPU/RSS telemetry, hardware-aware execution lineage, Model/Run/Compare efficiency surfaces, immutable 5-card PNG/PDF rendering and a real-Chrome CI gate.
- MCB-13 premium decision dashboard: planned; decision-first Overview, dataset drill-down, quality × latency/cost trade-offs, human-readable local execution context and premium progressive-disclosure UX.

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

The v2 core profile is task-vertical: 154 intent-classification cases, 154 OOS/calibration cases, 60 structured-output cases, 60 QA/abstention cases and 40 reasoning cases, for 468 cases per model.

Inspect the same suite across a local and API model without provider calls:

```bash
uv run python scripts/suite_inspect.py \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities all
```

## Plan and estimate before running

Inspect exact case counts and configured budgets without provider calls:

~~~bash
uv run model-bench plan --profile core --capabilities all
~~~

Run a small real pilot to project runtime/cost before committing to the full matrix:

~~~bash
uv run model-bench estimate \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --profile core \
  --capabilities all \
  --pilot-cases 5
~~~

The core configuration targets 28 minutes and has a 45-minute local hard guardrail per model. Its API target is USD 0.45 and hard guardrail USD 1.00 per model. API token cost is enriched from `pricing_snapshot.json` when a versioned price exists; otherwise it remains unknown rather than guessed.

See `MCB_10_VERTICAL_BENCHMARK_HARDENING.md` for benchmark-science details.

## Unified runner

The `model-bench` CLI executes the same capability matrix across local and API
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

New runs are stored by default under `results/runs/<run-id>`, while `run_group` remains a logical label. This preserves immutable cross-run history. To resume the exact same run, pass its existing `--run-id`; use `--retry-failures` to rerun only terminal failed cases.

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
paired same-case comparisons, family/difficulty breakdowns for controlled suites,
model/runtime metadata, exact case-attempt drill-down and infrastructure events.

A persisted run can be rendered again without provider credentials or a running runtime:

```bash
uv run model-bench report \
  --run-dir results/runs/<run-id>
```

Unknown provider cost remains `null`. The pricing snapshot is checksumed into each run manifest, and local hardware/runtime cost is intentionally separate from API token pricing.

See `MCB_8_REPORTING.md` for the evidence/report contract.

## What comes next

MCB-0…10 is implemented. The immediate gate is local automated validation followed by the controlled real-provider E2E: run `plan`, then `estimate`, and only then execute the same core slice through Korgis and an API model.

MCB-11 now provides typed lifecycle events, model/benchmark/execution signatures, latest-comparable CURRENT selection, a rebuildable DuckDB read model, typed dashboard payloads, the first Overview/Structured Output/Disagreement routes and immutable share snapshots.

MCB-13 now defines the next UI evolution: a premium decision dashboard that keeps benchmark-science guardrails while making overall quality, observed latency, known provider cost, dataset performance and local execution environment immediately legible. See `MCB_13_PREMIUM_DECISION_DASHBOARD.md`.

Build the cross-run read model and dashboard payloads without invoking a model:

~~~bash
uv run model-bench project --rebuild --export-dashboard
~~~

Build the single-file React dashboard using those projected payloads:

~~~bash
cd dashboard
npm ci
cd ..
uv run model-bench dashboard-build
~~~

Create an immutable result snapshot for sharing:

~~~bash
uv run model-bench share create \
  --capability structured-output \
  --models qwen3.5-2b-q4km,gpt-5.6-luna
~~~

The dashboard still falls back to clearly-labelled fixture data when no projected payload is injected, so demo numbers cannot be mistaken for real benchmark evidence. See `MCB_11_OBSERVABILITY_RESULTS_EXPLORER.md`.

Further benchmark-science enhancements remain a repeated performance microbenchmark, harder near-domain OOS cases and explicit parity-vs-native serving modes. Resource telemetry contracts are included in MCB-11 so the UI can expose local efficiency without conflating it with API cost.

Jev remains a bounded-decision suite on top of the same core. Its task semantics and rich
Jev-specific dashboard stay intentionally separate from the generic capability report.
