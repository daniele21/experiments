# VLM Capability Benchmark — Implementation Plan

## 1. Objective

Create a reusable benchmark for vision-language models that measures useful, inspectable capabilities rather than a single overall score.

The first version should answer:

- how well does a model extract and reason over documents and charts?
- how robustly does it answer visual questions?
- can it localize referenced objects/UI targets?
- what quality/latency/cost trade-off exists between local/open and API models?

The benchmark must run on top of `benchmark-core` and the shared multimodal primitives defined in `../MULTIMODAL_PARALLEL_PLAN.md`.

## 2. Initial capability matrix

### VLM-A — Document understanding

Candidate public family: DocVQA-like tasks.

Input:
- document image;
- question.

Output:
- short text or structured answer.

Metrics:
- exact/normalized match where valid;
- token/string similarity where appropriate;
- invalid response rate;
- latency;
- tokens/cost;
- visual evidence retained.

### VLM-B — Chart reasoning

Candidate public family: ChartQA-like tasks.

Input:
- chart image;
- question.

Output:
- number/text.

Metrics:
- exact normalized answer;
- numeric tolerance where explicitly allowed by task;
- invalid response rate;
- latency/tokens/cost.

### VLM-C — Visual reasoning

Candidate family: controlled diagrams plus public visual-reasoning datasets.

Goal:
separate pure OCR from relational/visual reasoning.

Metrics depend on task but should privilege observable final answers, not private chain of thought.

### VLM-D — Visual grounding

Input:
- image;
- textual referring expression.

Output:
- normalized bounding box or point.

Metrics:
- IoU;
- point-in-box / target hit rate;
- normalized coordinate validity;
- failure rate.

### VLM-E — UI understanding / grounding

Input:
- UI screenshot;
- user intent, e.g. "where should I click to create a project?"

Output:
- target label plus normalized click point/bounding box.

Metrics:
- hit rate;
- normalized coordinate distance;
- target element match;
- invalid coordinate rate.

This controlled UI task is particularly useful because failures are immediately visible in reports.

---

# 3. VLM-0 — Experiment skeleton

Create:

```text
experiments/vlm-capability-benchmark/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── models.yaml
├── runtimes.yaml
├── suite.yaml
├── profiles/
├── datasets/
├── tasks/
├── prompts/
├── src/
├── tests/
├── results/         # gitignored/generated
└── reports/         # gitignored/generated
```

No operational model IDs or paths should be hardcoded in Python.

Definition of Done:
- config validates without real credentials;
- fake VLM model can be resolved;
- smoke suite can be listed before any real provider exists.

---

# 4. VLM-1 — Dataset layer

Implement dataset adapters independently from providers.

Each dataset adapter declares:
- dataset ID/version;
- upstream source;
- pinned revision when possible;
- license/provenance;
- split;
- asset retrieval/cache policy;
- deterministic sampling;
- expected-output schema;
- checksum/fingerprint.

Start with two public/controlled families:
1. document/chart QA;
2. controlled UI grounding fixtures.

Then add public grounding and visual-reasoning datasets.

Tests:
- deterministic same-seed sample selection;
- no duplicate sample IDs;
- expected asset checksum;
- malformed/missing image failure;
- answer normalization fixtures.

Definition of Done:
- datasets can be loaded/tested offline from tiny committed fixtures;
- public dataset downloads are optional integration paths.

---

# 5. VLM-2 — Task contracts and evaluators

Implement task plugins that build multimodal `InferenceRequest` values using shared media refs.

Suggested interfaces:

```text
sample
  ↓
task request builder
  ↓
[text part + image part(s)]
  ↓
InferenceProvider
  ↓
normalized prediction
  ↓
task evaluator
```

Initial tasks:
- `document_qa`;
- `chart_qa`;
- `ui_grounding`.

Expansion:
- `visual_reasoning`;
- `object_grounding`.

Evaluator requirements:
- deterministic;
- no VLM-as-judge when exact/structural ground truth exists;
- explicit normalization;
- typed parse failures;
- metric metadata includes evaluator version.

Definition of Done:
- fake inference outputs fully exercise each evaluator;
- adding a task plugin does not modify matrix-loop code.

---

# 6. VLM-3 — Provider/runtime adapters

Provider work can proceed in parallel with VLM-1 and VLM-2 using the MM-0 contracts.

Initial target:
- one open/local Qwen VLM candidate;
- one API VLM comparator.

Runtime specifics must remain adapters/config, not task code.

Provider contract tests:
- image input;
- multiple image inputs if declared;
- text response;
- malformed provider response;
- timeout;
- unsupported media;
- usage metadata present/absent;
- model capability mismatch caught in preflight.

Local runtime telemetry where possible:
- model/artifact size;
- startup/load time;
- peak memory/VRAM;
- tokens/s;
- hardware fingerprint.

Definition of Done:
- task code is provider agnostic;
- model/runtime/provider identities are separately recorded.

---

# 7. VLM-4 — Matrix runner integration

Target command conceptually:

```bash
uv run vlm-bench run \
  --suite core-v1 \
  --models <model-a>,<model-b> \
  --profile smoke
```

Runner responsibilities:
- resolve suite;
- validate model capability requirements;
- preflight datasets/assets;
- execute model × task × sample matrix;
- persist raw evidence immediately;
- evaluate independently from provider inference;
- support resume by case identity when benchmark-core supports it.

The runner must not contain:
- model-family-specific branches;
- dataset-specific branches;
- evaluation-specific branches.

Definition of Done:
- same runner executes at least two task families.

---

# 8. VLM-5 — Reporting

The report should combine numbers with visual evidence.

Views:

### Capability matrix

```text
                    Model A   Model B
document QA
chart QA
UI grounding
visual reasoning
grounding
```

### Case drill-down

Show:
- input image;
- question/instruction;
- expected;
- model prediction;
- metric result;
- overlay marker/bounding box where applicable;
- latency/cost/resource metadata.

### Failure gallery

Group useful failure classes:
- OCR/text extraction;
- wrong numeric reasoning;
- target localization miss;
- invalid coordinates;
- hallucinated element;
- infrastructure/provider failure.

Do not hide failures in aggregate scores.

---

# 9. First vertical slice

Keep the first E2E narrow:

```text
Models
  - 1 local/open VLM
  - 1 API VLM

Tasks
  - chart/document QA
  - controlled UI grounding

Profiles
  - smoke
  - budget

Outputs
  - raw inference records
  - evaluation records
  - manifest
  - image-aware HTML report
```

This slice validates the architecture before expanding to more datasets.

---

# 10. Parallel work plan

After MM-0 contracts are stable:

### Stream A — datasets
- tiny controlled fixtures;
- dataset adapters;
- deterministic sampling;
- provenance.

### Stream B — tasks/evaluators
- document/chart QA parser;
- grounding coordinate schema;
- metrics.

### Stream C — providers
- open/local adapter;
- API adapter;
- preflight.

These streams converge only at VLM-4 runner integration.

Reporting can start early with fake records and placeholder images rather than waiting for real runs.

---

# 11. Test strategy

Cheap:
- unit evaluator tests;
- dataset fixture tests;
- config tests;
- fake-provider integration;
- artifact/report roundtrips.

Controlled:
- one real sample per provider/runtime.

Explicit E2E:
- smoke matrix;
- budget matrix;
- full public dataset runs.

---

# 12. Initial Definition of Done

VLM v1 is usable when:

1. at least 2 distinct VLM task families run;
2. at least one local/open and one API model can use the same task definitions;
3. UI grounding produces inspectable overlay output;
4. dataset revisions and image checksums are captured;
5. task metrics are deterministic;
6. reports expose both aggregates and individual visual failures;
7. no VLM-specific assumption leaks into the generic matrix runner.
