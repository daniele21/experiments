# MCB-1 — Generic Benchmark Contracts

Status: **IMPLEMENTED; CI validation pending**.

MCB-1 introduces the generic vocabulary that later workstreams will use to extract
infrastructure from `jev-vs-llm` without making Jev semantics part of the shared core.

## Contract boundaries

The shared package is `packages/benchmark-core`.

It is deliberately standard-library-only at runtime in this phase and does not import
`jev_bench`.

### Inference

`InferenceRequest` represents what is sent to a model runtime:

- request identity;
- raw input and/or messages;
- optional system prompt;
- optional response schema;
- generation configuration;
- task metadata.

`InferenceResult` represents provider/runtime evidence before task evaluation:

- provider and model identity;
- raw output;
- optional normalized output;
- latency;
- token usage;
- estimated API cost;
- validity;
- typed error;
- provider/runtime metadata.

The generic result does **not** contain `correct`, expected labels, accuracy or
task-specific decisions.

### Registry

The contracts explicitly separate:

```text
ModelSpec
   ↓ runtime_key
RuntimeSpec
   ↓ provider_key
ProviderSpec
```

This prevents "local", "Korgis", "OpenAI-compatible" and a concrete model from becoming one
hardcoded concept.

Model artifacts such as GGUF quantization are represented separately through
`ArtifactSpec`.

### Evaluation

`Sample`, `MetricResult` and `TaskResult` describe benchmark semantics after inference.

This intentionally separates:

```text
provider inference
      ↓
raw/normalized output
      ↓
task evaluator
      ↓
metrics
```

### Run provenance

`RunContext` and `RunManifest` establish the target provenance vocabulary for:

- run/group/suite;
- seed/profile;
- code version;
- benchmark-core version;
- model/runtime/provider;
- task/version;
- prompt/version;
- dataset/revision/split;
- sample-selection fingerprint;
- generation parameters;
- pricing metadata.

MCB-2 will connect these contracts to the existing manifest implementation.

## Jev compatibility bridge

The compatibility boundary lives in the Jev experiment, not in benchmark-core:

`jev_bench.generic_adapter.DecisionProviderInferenceAdapter`.

Direction:

```text
existing DecisionProvider
          ↓
DecisionProviderInferenceAdapter
          ↓
generic InferenceProvider
```

This direction is intentional.

It allows a future generic runner to execute existing Jev/OpenAI/Korgis/CLM decision
providers without changing their current prompts, parsing or decision semantics during the
first extraction phase.

The bridge uses `InferenceRequest.input` as the existing decision state and accepts
`QuestionSpec` objects through the namespaced metadata key `jev.questions`.

Those details remain inside `jev-vs-llm`; benchmark-core has no knowledge of them.

## Error model

Provider/runtime failures use `InferenceError` with a typed `kind`:

- configuration;
- authentication;
- timeout;
- transport;
- invalid_response;
- provider;
- unknown.

This lets MCB-7 later distinguish a wrong model answer from an infrastructure failure.

## Invariants

1. benchmark-core must never import an experiment package;
2. inference contracts must not assume classification or bounded decisions;
3. correctness belongs to evaluation, not inference;
4. model, runtime and provider identities stay separate;
5. invalid inference results require a typed error;
6. legacy compatibility lives at the experiment boundary;
7. new operational defaults remain configuration concerns, not hidden contract constants.

## MCB-1 Definition of Done

- [x] generic inference request/result contracts exist;
- [x] model/provider/runtime contracts exist;
- [x] sample/task/metric contracts exist;
- [x] run context/manifest contracts exist;
- [x] generic `InferenceProvider` protocol exists;
- [x] benchmark-core does not import `jev_bench`;
- [x] a fake provider can satisfy `InferenceProvider` structurally;
- [x] existing `DecisionProvider` can be exposed through a Jev-owned adapter;
- [ ] focused Ruff checks pass;
- [ ] generic contract tests pass;
- [ ] Jev characterization suite remains green.
