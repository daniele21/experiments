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
- MCB-4 task plugin registry: complete.

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

## What comes next

MCB-4 introduced the task plugin registry. MCB-5 now separates datasets from tasks. Once those
two boundaries are available, the first vertical slice will run the same local/API model
registry against BANKING77 classification and a controlled structured-output task.
