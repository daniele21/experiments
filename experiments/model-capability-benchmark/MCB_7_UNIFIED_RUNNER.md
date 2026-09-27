# MCB-7 — Unified Matrix Runner

Status: **IMPLEMENTED; controlled external-runtime validation pending**.

MCB-7 turns the declarative model/task/dataset/capability registries into one execution
path for local and API-hosted models.

## Architecture

```text
models.yaml + suite.yaml + tasks.yaml + datasets.yaml + profiles.yaml + runner.yaml
                                  |
                                  v
                         CapabilitySuiteBundle
                                  |
                                  v
                    model × capability × dataset
                                  |
                                  v
                          CapabilityRunner
                 +----------------+----------------+
                 |                                 |
                 v                                 v
        RegistryRuntimeResolver              EvidenceStore
                 |                                 |
        +--------+---------+             +---------+----------+
        |                  |             |         |          |
        v                  v             v         v          v
KorgisManagedRuntime  ExternalRuntime  state     raw     evaluation
        |                  |                       |
        +--------+---------+                       v
                 v                            aggregates
        provider factory
          |           |
          v           v
 OpenAI-compatible  OpenAI Responses
```

The main runner does not contain model-family, provider, task or dataset branches.

## CLI

The package exposes one entrypoint:

```bash
uv run model-bench models
uv run model-bench tasks
uv run model-bench datasets
uv run model-bench capabilities
uv run model-bench validate-config --models all
```

Execute a matrix:

```bash
uv run model-bench run \
  --run-group mcb7-smoke \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities structured-output,mathematical-reasoning \
  --profile smoke
```

Operational defaults live in `runner.yaml`, not in the execution loop.

## Runtime boundaries

### Korgis

MCB-7 manages **model residency**, not the Korgis server process.

For each selected Korgis model:

```text
health
  ↓
activate runtime_model_id
  ↓
run all selected capabilities
  ↓
unload runtime_model_id
```

This avoids duplicating the process-management implementation in `jev-vs-llm` and avoids
committing machine-specific paths.

The Korgis server must therefore already be running with its admin API enabled.

### API runtimes

API runtimes are external. The runner builds the configured provider adapter and performs
no lifecycle action on release.

Provider dispatch is based on `ProviderSpec.provider_type` and protocol metadata, not on
model names.

## Provider protocols

Supported in MCB-7:

- `openai-compatible / chat-completions` for Korgis and MiniCPM/ModelBest;
- `openai / responses` for OpenAI.

OpenAI-compatible providers receive the requested response schema in the prompt and request
JSON-object output for broad compatibility.

OpenAI Responses uses strict JSON Schema output when the task declares a schema.

## Failure semantics

MCB-7 distinguishes pipeline failure from model output quality.

### Completed case

A provider may return `InferenceResult(valid=False)`.

That is still observable model/provider evidence, so the runner:

1. persists raw inference evidence;
2. calls the evaluator;
3. persists evaluation evidence;
4. marks the case `completed`.

This contributes to validity/invalid-output metrics rather than being hidden as an
infrastructure crash.

### Failed case

An uncaught exception is tagged by stage:

- `request`;
- `provider`;
- `evaluation`.

Model-level failures are separate events:

- `runtime_prepare_failed`;
- `runtime_release_failed`;
- `dataset_load_failed`.

A failed model cannot erase already persisted evidence from earlier models.

## Incremental evidence

Every run-group directory contains append-only streams:

```text
state.jsonl
raw.jsonl
evaluation.jsonl
aggregates.jsonl
report_index.jsonl
events.jsonl
environment.json
run_manifest.json
```

### state.jsonl

Tracks case attempts:

```text
started -> completed
started -> failed
```

A case is resumable-complete only after the terminal `completed` state is persisted.

### raw.jsonl

Contains provider evidence, including:

- raw output;
- normalized output;
- latency;
- token usage;
- provider/model identity;
- known API cost;
- typed inference error.

### evaluation.jsonl

Contains:

- expected value;
- prediction;
- evaluator version;
- per-case metrics;
- task validity/error.

### aggregates.jsonl

Contains capability metrics for the selected model/capability matrix.

Unknown API cost remains `null`; it is never silently converted to zero.

### report_index.jsonl

Added by MCB-8 as the stable bridge from execution to reporting. Each model × capability
entry pins the exact `case_id + attempt` pairs used by the aggregate records, so a report
never drifts to a later retry or `--no-resume` attempt.
Korgis may report API/provider fee zero, which does not imply hardware/runtime cost zero.

## Resume

The runner builds a deterministic semantic `case_id` from:

- suite id/version;
- model and runtime identity;
- capability/task/prompt version;
- dataset revision/split;
- sample-selection fingerprint;
- sample id;
- profile;
- generation configuration;
- cross-dataset context fingerprints/checksums.

Therefore a prompt, dataset revision, selection or generation change produces a new
case identity and cannot accidentally reuse old evidence.

Default behavior:

- completed cases: skipped;
- failed terminal cases: skipped;
- `--retry-failures`: retry failed cases only;
- `--no-resume`: execute all selected cases as new attempts.

## Aggregate reducers

MCB-7 executes the reducers declared by MCB-6:

- mean;
- sum;
- rate;
- macro-F1;
- in-scope accuracy;
- OOS detection;
- top-label ECE;
- Brier-compatible mean component;
- p50;
- p95;
- invalid-rate.

Only terminal completed attempts are eligible for quality/latency aggregates.
Pipeline failures are counted separately as `failure_count`.

## Provenance

`environment.json` records environment and dependency provenance.

`run_manifest.json` records:

- run id/group;
- suite version;
- selected profile/seed;
- resolved model/runtime/provider identities;
- capability/task/dataset matrix;
- metric declarations;
- SHA-256 checksum of every authoritative YAML config;
- evidence artifact paths.

Credentials are never persisted.

## Controlled real-provider validation

This check is intentionally not part of per-commit CI because it needs a real local runtime
and incurs API/model cost.

Prerequisites:

```bash
export KORGIS_BASE_URL=http://127.0.0.1:1235/v1
export OPENAI_API_KEY=...
```

Start Korgis separately with the admin API enabled and make
`qwen3.5-2b-q4km` available in its model registry.

Validate configuration first:

```bash
uv run model-bench validate-config \
  --models qwen3.5-2b-q4km,gpt-5.6-luna
```

Then run the same two task families through both runtimes:

```bash
uv run model-bench run \
  --run-group mcb7-controlled-e2e \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities structured-output,mathematical-reasoning \
  --profile smoke
```

Re-run the exact command to verify resume; all completed cases should be skipped.

Retry only failed terminal cases:

```bash
uv run model-bench run \
  --run-group mcb7-controlled-e2e \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities structured-output,mathematical-reasoning \
  --profile smoke \
  --retry-failures
```

## Automated validation

CI covers:

- JSONL append/read;
- deterministic semantic case IDs;
- two-model fake E2E;
- incremental persistence;
- resume;
- retry-failures;
- invalid inference vs pipeline failure;
- aggregate reducers;
- OpenAI-compatible adapter contract;
- OpenAI Responses adapter contract;
- Korgis activate/unload lifecycle;
- runner defaults;
- environment/run manifest;
- CLI catalog/config smoke.

The real Korgis + external API execution remains an environmental validation step.
