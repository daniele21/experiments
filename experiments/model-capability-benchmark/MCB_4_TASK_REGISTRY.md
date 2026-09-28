# MCB-4 — Task Registry and Plugin Protocol

Status: **COMPLETE** — focused task registry gate green and all cumulative MCB/VLM/image-generation gates green.

## Goal

Make benchmark tasks extensible without adding task-specific branches to the matrix runner.

The central runner should operate on a single protocol:

```text
Sample
  ↓
BenchmarkTask.build_request
  ↓
InferenceRequest
  ↓
InferenceProvider
  ↓
InferenceResult
  ↓
BenchmarkTask.evaluate
  ↓
TaskResult
```

The runner does not need to know whether the task is classification, structured extraction,
visual grounding, QA or image generation.

## Separation from datasets

The initial implementation plan proposed `load_samples` on the task interface. MCB-4
deliberately tightens that design.

A task **does not load datasets**.

Dataset loading, versioning, sampling and normalization belong to MCB-5. A task receives a
normalized `Sample` and owns only:

- request construction;
- output interpretation/evaluation;
- task-level metrics.

This prevents task and dataset lifecycles from being coupled.

## Shared contracts

`benchmark_core.tasks` introduces:

- `TaskSpec`;
- `TaskMetricSpec`;
- `TaskExecutionContext`;
- `BenchmarkTask` protocol;
- `TaskPluginRegistry`;
- `TaskRegistry`;
- strict YAML task-spec loading.

### TaskSpec

A task definition declares:

- task id and version;
- plugin id;
- evaluator id and version;
- required model capabilities;
- compatible dataset IDs;
- prompt id and version;
- metric declarations;
- task options.

Prompt id/version must be provided together. This makes prompt identity explicit rather
than allowing an unversioned prompt to silently affect benchmark results.

### BenchmarkTask

A plugin implements only:

```python
build_request(sample, context) -> InferenceRequest
evaluate(sample, inference, context) -> TaskResult
```

The protocol is structural, so experiment packages own their task implementation without a
dependency from benchmark-core back to the experiment.

### Plugin registry

`TaskPluginRegistry` maps a declarative `plugin_id` to a factory.

`TaskRegistry.from_specs` instantiates the catalog once. The matrix runner later asks the
registry for a task; it never branches on task family.

The plugin registry also fails closed when:

- a plugin is missing;
- a plugin id is duplicated;
- a plugin changes the authoritative TaskSpec;
- a task registry key and task id disagree.

## Capability preflight

Task requirements use the same `ModelCapabilities` contract already shared by text, VLM
and image-generation tracks.

`TaskRegistry.validate_model` delegates to the shared capability validator.

Examples:

- text classification requires `text_input`;
- VLM grounding can require `text_input + image_input`;
- text-to-image can require `text_input + image_output`.

This means multimodal task families do not need a second task registry.

## Dataset compatibility

`TaskRegistry.validate_dataset` checks the selected dataset before inference begins.

The current task catalog declares:

- `intent-classification` → `banking77`;
- `structured-output` → `structured-output-controlled-v1`.

MCB-5 will provide the corresponding dataset adapters.

## First concrete plugins

The model capability suite contains two experiment-owned plugins.

### IntentClassificationTask

It:

- reads the candidate labels from normalized sample metadata;
- creates a strict JSON response schema dynamically;
- keeps prompt instructions in `tasks.yaml`;
- scores per-case accuracy.

It has no BANKING77 loader or hardcoded BANKING77 label list.

### StructuredOutputTask

It:

- reads the response schema from normalized sample metadata;
- creates the inference request;
- evaluates schema/object validity;
- measures expected-field accuracy;
- counts hallucinated fields.

The controlled dataset itself is deferred to MCB-5.

## Configuration-first rules

`tasks.yaml` owns:

- task/plugin identifiers;
- versions;
- evaluator identity/version;
- prompt identity/version;
- compatible datasets;
- capability requirements;
- metrics;
- operational task options/instructions.

The Python runner must not contain `if task == "classification"` or equivalent routing.

## Operational inspection

`scripts/task_inspect.py` loads the declarative catalog through the same plugin bootstrap
used by tests and emits JSON describing:

- tasks;
- plugin ids;
- versions;
- evaluator versions;
- prompt versions;
- datasets;
- capabilities;
- metrics.

## Definition of Done

- [x] generic BenchmarkTask protocol exists;
- [x] TaskSpec is versioned and capability-aware;
- [x] strict declarative task catalog loader exists;
- [x] plugin factories are separated from the runner;
- [x] duplicate/missing plugins fail closed;
- [x] dataset compatibility can be checked before inference;
- [x] model capabilities can be checked before inference;
- [x] task/evaluator/prompt versions are explicit in task metadata;
- [x] classification plugin is provider-independent;
- [x] structured-output plugin is provider-independent;
- [x] task catalog inspection CLI exists;
- [x] focused MCB-4 CI passes;
- [x] previous MCB/VLM/image-generation gates remain green;
- [x] full Jev characterization suite remains green.
