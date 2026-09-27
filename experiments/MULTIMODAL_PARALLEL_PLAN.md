# Multimodal Benchmarks — Parallel Implementation Plan

## 1. Goal

Add two independent experimental tracks to `experiments`:

1. `vlm-capability-benchmark`: evaluate vision-language models on observable multimodal understanding tasks.
2. `image-generation-benchmark`: compare image-generation and image-editing models with reproducible prompt suites, automatic metrics where valid, and visual/human evaluation.

Both tracks must reuse `packages/benchmark-core`. They must not introduce separate orchestration stacks.

The target architecture is:

```text
                         benchmark-core
                              |
                    multimodal primitives
                  /                       \
                 /                         \
vlm-capability-benchmark          image-generation-benchmark
  image -> text/structure           text/image -> image
```

## 2. Architectural principles

### P1 — One shared multimodal foundation

Only generic capabilities belong in `benchmark-core`: media references, typed multimodal content, output artifacts, capability declaration, persistence metadata and generic report data.

VLM task semantics, image-generation prompts and model-specific behavior stay in their experiment folders.

### P2 — Asset references, not binary blobs in records

Run/evaluation records must refer to immutable media artifacts through stable IDs/paths plus checksum and metadata. CSV/JSON records must not embed base64 images.

### P3 — Configuration first

Model IDs, providers, endpoints, local model paths, prompt sets, dataset revisions, generation settings, image sizes, seeds, retries and evaluator selections must be config/registry driven.

### P4 — Raw evidence first

Every run preserves:
- original sample/prompt reference;
- input asset references;
- raw provider output metadata;
- generated/output artifact references;
- latency and cost where available;
- effective generation parameters;
- evaluator outputs;
- human-evaluation records when present;
- run manifest and code revision.

### P5 — No opaque global winner

Reports compare models by capability/task and expose examples/failure cases. A human preference win rate may be shown for a defined prompt suite, but it must not replace per-task evidence.

### P6 — Expensive E2E runs are explicit

Unit/contract tests run routinely. Real-model VLM and image-generation matrices are controlled E2E runs and must not run for every commit.

---

## 3. Shared gate: MM-0 multimodal core extension

This is the only work that should block both tracks.

### 3.1 Contracts

Extend `benchmark-core` with typed primitives similar to:

```python
MediaRef(
    media_id,
    media_type,          # image initially; video can come later
    uri_or_path,
    mime_type,
    sha256,
    width,
    height,
    metadata,
)

ContentPart(
    kind,                # text | image
    text=None,
    media=None,
)

OutputArtifact(
    artifact_id,
    media_type,
    path,
    mime_type,
    sha256,
    width,
    height,
    metadata,
)
```

`InferenceRequest` must support multimodal content without breaking current text users.

`InferenceResult` must support output artifacts in addition to textual/raw output.

### 3.2 Model/runtime capability declaration

Registry metadata should be able to declare at least:

```yaml
capabilities:
  text_input: true
  image_input: true
  image_output: false
  image_editing: false
  multi_image_input: true
```

Preflight must fail before a run if task requirements are incompatible with a selected model/runtime.

### 3.3 Artifact store

Add a small generic artifact layer:
- deterministic run directory;
- immutable artifact filenames/IDs;
- SHA-256;
- image metadata;
- no binary content in CSV;
- relative references suitable for HTML reports;
- optional provider URL copied to a local artifact only when the provider permits retrieval.

### 3.4 Generic reporting support

Expose enough report data to render:
- input images;
- output images;
- side-by-side model comparisons;
- evaluator metric panels;
- failure annotations.

The experiment owns the final report layout.

### 3.5 Tests

Contract tests:
- text-only backward compatibility;
- image input request;
- image output artifact;
- missing file / invalid MIME;
- checksum stability;
- provider capability mismatch;
- artifact references survive persistence roundtrip.

### MM-0 Definition of Done

- existing Jev/model benchmark text tests remain green;
- a fake VLM provider can receive an image reference and return text;
- a fake image provider can return a generated image artifact;
- artifacts are persisted outside row-oriented records;
- no model/provider-specific logic is added to the core.

---

# 4. Track A — VLM capability benchmark

Detailed plan: `experiments/vlm-capability-benchmark/IMPLEMENTATION_PLAN.md`.

Initial capability families:

1. document understanding;
2. chart reasoning;
3. visual reasoning;
4. visual/object grounding;
5. UI understanding/grounding.

Initial candidate open baseline: Qwen VLM family; closed/API comparators may be added through the same provider contracts.

The first vertical slice should be intentionally small:

```text
1 open/local VLM + 1 API VLM
          x
Doc/Chart QA + controlled UI grounding
          ↓
raw evidence + automatic metrics + visual report
```

---

# 5. Track B — Image generation benchmark

Detailed plan: `experiments/image-generation-benchmark/IMPLEMENTATION_PLAN.md`.

Initial capability families:

1. exact text rendering;
2. compositional prompt adherence;
3. photorealistic generation;
4. illustration/design;
5. image editing/preservation;
6. later: subject/reference consistency and transparent-background generation.

Initial candidate models:
- GPT image provider;
- Gemini image provider;
- Qwen-Image-2.1 as open/local candidate where the selected runtime supports it.

The first vertical slice:

```text
GPT image + Gemini image
          x
text rendering + prompt adherence
          ↓
automatic checks + blind side-by-side gallery
```

Then add Qwen-Image-2.1 and editing.

---

# 6. Parallel execution model

## Phase 0 — shared gate

```text
MM-0A contracts/assets
        |
        +------ MM-0B artifact persistence
        |
        +------ MM-0C capability/preflight
        |
        +------ MM-0D report primitives
```

These four substreams can mostly run in parallel after the media/artifact data shapes are agreed.

Only the contract shape itself is a short sequential decision.

## Phase 1 — two tracks start in parallel

```text
                 MM-0 stable contracts
                      /       \
                     /         \
                    v           v
             VLM Track          IMG Track
```

### VLM Track internal parallelism

```text
VLM-1 dataset adapters -----------+
VLM-2 task/evaluator contracts ---+--> VLM-4 runner integration
VLM-3 provider adapters ----------+          |
                                             v
                                      VLM-5 report + E2E
```

Dataset work does not need to wait for real providers if fake-provider fixtures are used.

### Image generation internal parallelism

```text
IMG-1 prompt suite ---------------+
IMG-2 provider adapters ----------+--> IMG-4 matrix runner
IMG-3 evaluator/human schema -----+          |
                                             v
                                      IMG-5 visual report + E2E
```

Prompt-suite authoring, provider adapters and evaluator development are independent once artifact contracts are fixed.

---

# 7. Recommended delivery batches

## Batch 1 — foundation

- MM-0 multimodal contracts;
- artifact store;
- capability/preflight;
- fake provider contract tests.

This batch should be small and merged early because both tracks depend on it.

## Batch 2A — VLM vertical slice

In parallel:
- controlled datasets/fixtures;
- first VLM provider;
- Doc/Chart QA evaluators;
- controlled UI grounding task.

Assemble only after each component has independent tests.

## Batch 2B — Image generation vertical slice

In parallel:
- prompt suite v1;
- GPT image provider adapter;
- Gemini image provider adapter;
- OCR/text-rendering evaluator;
- prompt-constraint evaluator;
- blind-comparison record schema.

## Batch 3A — VLM expansion

- public dataset adapters with pinned revisions/licenses;
- Qwen local runtime integration;
- grounding;
- visual reasoning;
- report drill-down.

## Batch 3B — Image generation expansion

- Qwen-Image-2.1 adapter/runtime;
- editing/preservation suite;
- reference consistency;
- stronger human pairwise workflow;
- richer gallery/failure views.

## Batch 4 — convergence

Reuse generic improvements discovered by both tracks:
- resume;
- cost/resource telemetry;
- shared HTML media components;
- unified manifest fields;
- documentation for adding a multimodal model/task/provider.

---

# 8. Ownership boundaries

### benchmark-core owns

- media/content contracts;
- output artifact references;
- generic model/runtime capability flags;
- common run identity/manifest;
- persistence primitives;
- generic telemetry;
- reusable HTML/report data primitives.

### VLM experiment owns

- VLM datasets;
- multimodal QA/grounding prompts;
- answer parsing;
- task-specific metrics;
- VLM-specific report interpretation.

### Image-generation experiment owns

- prompt suites;
- image-generation/edit provider mappings;
- generation-specific parameters;
- image evaluators;
- human blind-comparison schema;
- visual gallery/report semantics.

This separation prevents `benchmark-core` from becoming a catch-all multimodal application.

---

# 9. Branching and integration strategy

Prefer short-lived branches by dependency slice, not one long branch per entire track.

Suggested sequence:

```text
feat/mm-core-contracts
feat/mm-artifacts
feat/vlm-datasets
feat/vlm-providers
feat/vlm-evaluators
feat/imagegen-prompts
feat/imagegen-providers
feat/imagegen-evaluators
feat/vlm-reporting
feat/imagegen-reporting
```

Avoid concurrent edits to the same core files by giving MM-0 a clear owner/order.

The two experiment folders can otherwise progress independently.

---

# 10. Test strategy

### Cheap on every relevant PR

- contract/unit tests;
- config validation;
- deterministic prompt/sample selection;
- evaluator tests with committed tiny fixtures;
- report rendering with synthetic images;
- static anti-hardcoding checks where practical.

### Controlled

- one real VLM smoke model;
- one real image provider smoke call;
- provider authentication/connectivity smoke.

### Explicit E2E

- full model × task matrices;
- image-generation suites with multiple outputs/seeds;
- human preference campaigns.

---

# 11. Immediate implementation order

1. Finish/stabilize the remaining MCB-2 transport work enough that the shared provider boundary is not moving underneath MM-0.
2. Implement MM-0 contracts and artifact persistence.
3. In parallel start:
   - VLM controlled fixtures + task/evaluator definitions;
   - image-generation prompt suite + evaluator specifications.
4. Once MM-0 lands, wire providers in parallel.
5. Assemble two independent smoke E2Es.
6. Only after both vertical slices work, add broader public datasets/models and richer reporting.

This minimizes rework while still maximizing parallelism.

---

# 12. Success criteria

The multimodal workstream is healthy when:

1. adding a VLM does not require editing the VLM runner;
2. adding an image generator does not require editing the image-generation runner;
3. the same artifact/provenance primitives are used by both tracks;
4. model/runtime capability mismatches fail in preflight;
5. all generated/input images are traceable to immutable artifacts/checksums;
6. VLM reports show metrics plus inspectable visual evidence;
7. image-generation reports show blind side-by-side outputs plus objective metrics where meaningful;
8. no single subjective score is presented as ground truth;
9. real-model E2Es are optional and separated from normal PR checks;
10. existing text experiments remain backwards compatible.
