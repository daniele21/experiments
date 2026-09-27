# MCB-3 — Unified Model / Runtime / Provider Registry

Status: **IMPLEMENTED; CI validation pending**.

## Goal

Make local and remote models first-class peers without encoding provider/runtime branches
inside the benchmark runner.

The registry hierarchy is:

```text
model key
   ↓
ModelSpec
   ↓ runtime_key
RuntimeSpec
   ↓ provider_key
ProviderSpec
```

The resolver returns all three contracts as one `ResolvedModel` while preserving their
separate identities.

## Registry file

The model capability suite uses:

`experiments/model-capability-benchmark/models.yaml`

It contains top-level sections:

- `providers`;
- `runtimes`;
- `models`.

No API keys or machine-specific filesystem paths are permitted.

## ProviderSpec

A provider declares connection semantics, not a model.

Relevant fields:

- provider key;
- provider type;
- optional base URL environment variable;
- optional API key environment variable;
- explicit required environment variables;
- provider options.

The actual secret value is never part of the registry.

## RuntimeSpec

A runtime connects a provider with a deployment/lifecycle mode.

Current deployment values:

- `local`;
- `api`;
- `remote`;
- `hybrid`.

Current lifecycle values:

- `external`;
- `managed`;
- `persistent`.

The contracts reject unsupported values instead of trusting type hints only.

## ModelSpec

A model declares:

- stable model key;
- canonical `model_id`;
- runtime key;
- optional runtime-facing `runtime_model_id`;
- family;
- parameter count;
- artifact metadata;
- tags;
- model metadata.

### Canonical ID vs runtime ID

This distinction is required for managed local runtimes.

For example:

```text
canonical: unsloth/qwen3.5-2b
runtime:   qwen3.5-2b-q4km
```

Korgis can activate/use the runtime alias while benchmark manifests still preserve the
canonical identity.

API models normally omit `runtime_model_id`, so the canonical `model_id` is used
directly.

## Resolution

`RegistryBundle.resolve(model_key)` returns:

```text
ResolvedModel
├── model
├── runtime
└── provider
```

`ResolvedModel.effective_model_id` resolves to:

```text
runtime_model_id if present
otherwise model_id
```

The registry fails closed when:

- a model references an unknown runtime;
- a runtime references an unknown provider;
- a deployment/lifecycle value is unsupported;
- a registry object has an unknown field;
- required sections are missing or malformed.

Unknown fields are rejected intentionally so typos cannot silently alter benchmark
configuration.

## Selection

The core supports declarative selection by:

- explicit model keys;
- tags;
- deployment;
- family;
- maximum parameter count;
- quantization.

No model-family-specific branch is needed in the selection loop.

## Preflight

`preflight_models` validates only the selected models.

This means selecting a local Korgis model does not require an OpenAI key, while selecting
an OpenAI API model fails before execution when `OPENAI_API_KEY` is absent.

Preflight issues carry:

- issue code;
- model key;
- runtime key;
- provider key;
- environment variable;
- actionable message.

This is the boundary the future unified runner will call before activating a model or
loading a dataset.

## First committed registry

The initial registry contains:

- Qwen3.5 2B Q4_K_M on managed Korgis;
- Nemotron Nano 4B Q4_K_M on managed Korgis;
- GPT-5.6 Luna through the OpenAI API runtime;
- MiniCPM-V-4.6-1B through the ModelBest API runtime.

The purpose is architectural coverage, not a final benchmark matrix.

## Legacy Jev registry

`jev-vs-llm/benchmark-models.yaml` remains untouched in MCB-3 because it is currently
consumed by the Korgis/local-llm lifecycle and contains runtime-machine paths.

The new unified registry deliberately does not copy those paths.

Migration of Jev lifecycle/config consumption to the shared registry belongs to the
consolidation path after the generic runtime/task runner is available; it must not be done
by breaking current Jev runs.

## CLI

`scripts/registry_inspect.py` provides a runner-independent way to:

- resolve models;
- apply filters;
- inspect effective runtime IDs;
- run environment preflight;
- emit machine-readable JSON.

This is also the first consumer proving that local and API models pass through the same
registry resolution path.

## Definition of Done

- [x] typed provider/runtime/model registry loader exists;
- [x] referential integrity is validated;
- [x] unknown config fields fail closed;
- [x] canonical and runtime-facing model IDs are distinct;
- [x] declarative model filters exist;
- [x] preflight is selection-scoped;
- [x] committed registry has no API keys;
- [x] committed registry has no machine-specific model paths;
- [x] one Korgis model and one API model resolve through the same path;
- [x] registry inspection/preflight CLI exists;
- [ ] focused MCB-3 CI passes;
- [ ] previous MCB gates remain green;
- [ ] full Jev characterization suite remains green.
