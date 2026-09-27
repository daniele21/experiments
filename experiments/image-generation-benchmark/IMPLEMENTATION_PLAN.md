# Image Generation Benchmark — Implementation Plan

## 1. Objective

Create a reproducible image-generation benchmark that makes differences between models easy to inspect visually while preserving structured evidence.

The benchmark should initially compare API image models such as GPT image and Gemini image, then add an open/local candidate such as Qwen-Image-2.1 when the runtime path is ready.

The goal is not to produce a single "best image model" score. The goal is to expose where models differ by capability, with:
- identical prompts;
- controlled generation settings where comparable;
- automatic evaluation only where meaningful;
- blind human pairwise evaluation for subjective dimensions;
- side-by-side galleries and failure cases.

It must reuse `benchmark-core` and the shared multimodal primitives defined in `../MULTIMODAL_PARALLEL_PLAN.md`.

---

# 2. Initial capability families

## IMG-A — Exact text rendering

Examples:
- storefront signs;
- posters;
- pricing cards;
- product labels;
- UI-like cards.

Each prompt contains an exact target string.

Metrics:
- OCR exact match;
- character error rate / normalized string accuracy;
- word accuracy;
- readability/human preference;
- prompt constraint satisfaction;
- latency/cost.

This should be one of the first tasks because it is visually obvious and partly objective.

## IMG-B — Compositional prompt adherence

Prompts encode explicit constraints:
- object identity;
- count;
- color;
- relative position;
- required/forbidden elements;
- optionally exact text.

Example expectation is stored as structured constraints rather than prose only.

Metrics:
- constraint satisfaction rate;
- missing requested elements;
- extra/hallucinated elements;
- spatial relation correctness;
- human preference as a separate field.

## IMG-C — Photorealistic generation

Prompt families:
- portrait/lifestyle;
- product/still life;
- interiors;
- urban/night scenes.

Evaluation:
- blind human preference;
- structured artifact/failure annotations;
- optional VLM judge as secondary evidence, never sole truth.

Do not pretend photorealism has a universally objective scalar metric.

## IMG-D — Illustration/design

Prompt families:
- editorial illustration;
- flat/vector-like composition;
- marketing creative;
- poster;
- SaaS/technology hero visual.

Evaluation:
- blind pairwise preference;
- instruction adherence;
- typography when present;
- structured human rubric.

## IMG-E — Image editing and preservation

Input:
- source image;
- edit instruction.

Examples:
- change one object color;
- remove one object;
- replace background;
- add one object while preserving the rest.

Separate metrics:
1. edit success;
2. preservation of untouched regions;
3. artifacts introduced;
4. human preference.

The two objectives must not be collapsed into one opaque score.

## Later extensions

- subject/reference consistency;
- multi-reference composition;
- transparent-background/RGBA generation;
- UI mockup generation;
- iterative editing.

---

# 3. IMG-0 — Experiment skeleton

Create:

```text
experiments/image-generation-benchmark/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── models.yaml
├── runtimes.yaml
├── suite.yaml
├── profiles/
├── prompt_suites/
├── evaluators/
├── assets/
├── src/
├── tests/
├── results/         # generated/gitignored
└── reports/         # generated/gitignored
```

Configuration must own:
- provider/model IDs;
- requested output size/aspect ratio;
- number of samples per prompt;
- seed when supported;
- quality/style parameters when supported;
- retries/timeouts;
- evaluator selection;
- output paths.

Provider-specific options go into provider/runtime config, not prompt definitions.

---

# 4. IMG-1 — Prompt suite v1

Author prompt cases independently from providers.

Each case should have a stable schema, e.g.:

```yaml
prompt_id: text_001
category: text_rendering
difficulty: medium
prompt: >
  Create a clean storefront sign for a coffee shop.
  The sign must display exactly: "CAFFÈ CENTRALE"
expectations:
  exact_text:
    - "CAFFÈ CENTRALE"
  semantic_constraints:
    - storefront_sign
negative_constraints: []
evaluation:
  - ocr_exact
  - human_pairwise
```

For compositional tasks, expectations should be machine-readable:

```yaml
expectations:
  objects:
    - id: cube
      type: cube
      color: red
    - id: sphere
      type: sphere
      color: blue
  relations:
    - left_of: [cube, sphere]
```

Initial suite target:
- 5 text-rendering prompts;
- 5 compositional prompts;
- 5 photorealistic prompts;
- 5 design/illustration prompts.

First smoke suite may use only 2–3 per category.

Version prompt suites explicitly.

Definition of Done:
- prompt selection is deterministic;
- expectations are schema validated;
- no model-specific prompt variants in v1 unless explicitly modeled as protocol variants.

---

# 5. IMG-2 — Provider adapters

Provider adapters transform the common generation request into provider-specific API/runtime calls and persist output artifacts.

Initial parallel targets:
- GPT image adapter;
- Gemini image adapter.

Later:
- Qwen-Image-2.1 open/local adapter.

Provider adapter responsibilities:
- map common request fields;
- validate supported features;
- call provider/runtime;
- download/materialize output where allowed;
- emit `OutputArtifact`;
- capture provider metadata, latency and known cost;
- normalize typed errors.

Provider adapter must not:
- evaluate visual quality;
- know prompt-suite semantics;
- write report-specific HTML;
- silently rewrite prompts.

Capability declaration examples:
- text-to-image;
- image-edit;
- multi-image reference;
- transparent output;
- seed support;
- supported aspect/size modes.

Unsupported combinations fail in preflight.

---

# 6. IMG-3 — Evaluation layer

Evaluation is deliberately multi-source.

## 6.1 Deterministic/automatic metrics

Use only where the task has measurable ground truth.

### Text rendering
- OCR extracted text;
- exact normalized string match;
- character-level similarity;
- missing/extra text.

### Prompt constraints
Where robust detectors/parsers exist:
- required object presence;
- count;
- color;
- simple spatial relation.

Automatic evaluators must persist their own version and raw evidence.

## 6.2 VLM-as-judge

Allowed as secondary evaluator for dimensions such as instruction adherence, but:
- judge model/version must be recorded;
- rubric must be versioned;
- output must be structured;
- do not use it as the only source for subjective visual preference;
- keep judge results separate from human judgments.

## 6.3 Human blind pairwise evaluation

This is a first-class part of the experiment, not an afterthought.

For each prompt:
- randomize left/right model assignment;
- hide provider/model identity;
- retain the randomization key for analysis;
- ask capability-specific questions.

Example fields:
- prompt adherence: A / B / tie;
- visual preference: A / B / tie;
- text quality when relevant: A / B / tie;
- artifact severity;
- optional notes.

Store votes as independent records so multiple reviewers can be aggregated later.

Definition of Done:
- human evaluation can be performed without exposing model identity;
- automatic and human evidence are kept separate.

---

# 7. IMG-4 — Matrix runner

Conceptual UX:

```bash
uv run image-bench run \
  --suite core-v1 \
  --models <gpt-image>,<gemini-image> \
  --profile smoke
```

Runner resolves:
```text
model × prompt × repetition/seed
```

Per case:
1. resolve prompt;
2. validate model capability;
3. invoke provider;
4. persist generated artifact immediately;
5. persist raw metadata;
6. run configured automatic evaluators;
7. prepare blind-comparison records.

Generation failures remain distinct from low-quality outputs.

Runner must support repeated generations per prompt because image generation is stochastic.

Recommended profiles:
- `smoke`: 1 output × small prompt subset;
- `budget`: 1 output × full v1 prompt suite;
- `robust`: multiple outputs per prompt;
- `full`: explicitly controlled expensive run.

---

# 8. IMG-5 — Visual report

The report is a primary product of this benchmark.

## 8.1 Side-by-side gallery

For each prompt:
- exact prompt;
- expectations;
- generated images;
- model identity shown only in post-evaluation/report mode;
- automatic metric badges;
- latency/cost metadata.

## 8.2 Blind evaluation mode

A separate view/export should show:
- prompt;
- Image A;
- Image B;
- evaluation controls/schema;
- no model identity.

Avoid fixed left/right assignment across prompts.

## 8.3 Capability summary

Show separate matrices for:
- text rendering;
- prompt adherence;
- photorealistic preference;
- design preference;
- editing success/preservation.

## 8.4 Failure gallery

Useful failure tags:
- misspelled text;
- missing object;
- wrong count;
- wrong spatial relation;
- unintended extra object;
- anatomical artifact;
- edit spillover;
- background corruption;
- provider failure.

Visual evidence should be directly inspectable.

---

# 9. IMG-6 — Editing benchmark

Add after text-to-image vertical slice is stable.

Case schema includes:
- source image artifact;
- edit instruction;
- target edit mask/region where available;
- preservation region/expectations;
- expected semantic change.

Metrics:
- requested edit success;
- preservation outside edit region;
- artifact severity;
- blind human preference.

Initial controlled cases should use synthetic/simple scenes where edit success is easy to verify.

Then add more realistic editing tasks.

---

# 10. First vertical slice

Use only two providers initially:

```text
GPT image
Gemini image
    x
5 text-rendering prompts
5 compositional prompts
    x
1 output per prompt
```

Outputs:
- 20 generated images;
- automatic OCR/constraint evidence;
- manifest;
- blind side-by-side comparison package/view;
- visual report.

This validates the benchmark before adding expensive/stochastic breadth.

Afterwards:
1. add multiple repetitions;
2. add photorealism/design;
3. add Qwen-Image-2.1;
4. add editing.

---

# 11. Parallel work plan

After MM-0 artifact contracts are stable:

### Stream A — Prompt suite
- schema;
- v1 prompt cases;
- expectation validators;
- prompt versioning.

### Stream B — Provider adapters
- GPT image;
- Gemini image;
- fake image provider for tests.

### Stream C — Evaluation
- OCR evaluator;
- constraint evaluator;
- human vote schema/randomization.

### Stream D — Reporting
Can begin immediately from synthetic/fake image artifacts:
- gallery;
- blind pairwise layout;
- metric panels.

Streams converge at IMG-4 matrix runner.

Qwen integration does not block the first comparison.

---

# 12. Reproducibility and fairness rules

Image providers expose different controls, so the benchmark must record rather than hide those differences.

Always capture:
- exact prompt;
- provider/model/version identity where available;
- requested size/aspect ratio;
- actual output dimensions;
- seed if provider supports it;
- generation parameters;
- number of outputs;
- date/time;
- API/runtime metadata;
- pricing snapshot;
- artifact checksum.

Do not claim seed-equivalent reproducibility across providers that do not support the same controls.

For visual comparison:
- use same semantic prompt;
- request closest comparable aspect ratio/size;
- disclose when provider-specific constraints differ.

---

# 13. Test strategy

Cheap:
- prompt-schema validation;
- deterministic case selection;
- fake provider artifact creation;
- OCR normalization fixtures;
- human-pair randomization tests;
- report render tests.

Controlled:
- one real prompt per API provider.

Explicit E2E:
- full prompt suite;
- repeated generations;
- editing suite;
- open/local Qwen run.

---

# 14. Initial Definition of Done

Image-generation v1 is usable when:

1. GPT image and Gemini image can run from the same prompt suite;
2. generated images are persisted as immutable artifacts;
3. exact-text and compositional tasks have structured automatic evidence;
4. subjective preference is collected blind and separately;
5. side-by-side reports make differences visually obvious;
6. failures can be inspected per prompt;
7. adding Qwen-Image-2.1 requires a new adapter/config, not changes to the runner;
8. no operational generation setting is hidden/hardcoded in Python.
