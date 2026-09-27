# MCB-6 — Capability Suite

Status: **IMPLEMENTED; CI validation pending**.

MCB-6 composes the model, task and dataset registries into the first complete,
versioned capability suite.

## Suite

The authoritative declaration is:

`experiments/model-capability-benchmark/suite.yaml`

It defines:

- suite id/version;
- default profile;
- generation parameters;
- capability -> task -> dataset composition;
- one primary metric per capability;
- secondary quality/validity/latency/token/cost metrics;
- reducer semantics;
- capability-level context bindings.

No model, task or dataset branch is encoded in a runner.

## Initial capability matrix

The v1 suite contains five capabilities.

| Capability | Task | Dataset(s) | Primary metric |
|---|---|---|---|
| intent classification | intent-classification | BANKING77 | accuracy |
| OOS / calibration | calibrated-intent-classification | BANKING77 + CLINC150 OOS | OOS detection rate |
| structured output | structured-output | controlled structured output | schema-valid rate |
| QA + abstention | qa-abstention | controlled QA | exact match |
| mathematical reasoning | mathematical-reasoning | controlled math | final-answer accuracy |

This exceeds the original minimum of four capabilities and spans four distinct task
families.

## Capability metric contract

`benchmark_core.suites` now distinguishes:

- `task_metric`: values emitted by `TaskResult.metrics`;
- `evaluation`: aggregate metrics derived from expected/predicted evaluation records;
- `inference`: transport/model evidence such as validity, latency, tokens and cost.

Supported reducer declarations are currently:

- mean;
- sum;
- rate;
- macro F1;
- in-scope accuracy;
- OOS detection;
- ECE;
- Brier;
- p50;
- p95;
- invalid-rate.

MCB-6 validates that these declarations are known and internally consistent.

The reducers are **declarative in MCB-6**. Their execution over persisted records belongs
to the MCB-7 unified runner / aggregation path. This keeps suite definition separate from
execution orchestration.

## OOS and calibration semantics

The OOS capability uses:

- BANKING77 as in-scope intent space;
- filtered CLINC150 `oos_test` evidence;
- explicit `other` label;
- top-label confidence in [0, 1].

The task emits per-case:

- correctness;
- confidence;
- OOS decision correctness;
- squared error between top-label confidence and the correctness event.

The suite calls the aggregate of that final quantity
`brier_correctness`.

This is intentionally **not described as a full multiclass Brier score**, because the
current protocol requests only the selected label and its confidence, not a probability
distribution over all 78 labels.

ECE is likewise top-label ECE: confidence is calibrated against whether the selected label
was correct.

## Declarative capability context

CLINC150 samples should not know about BANKING77 labels, and the runner should not contain
a special-case branch for calibration.

MCB-6 therefore adds a typed capability context binding.

The OOS suite declares conceptually:

```yaml
context:
  labels:
    source: dataset_metadata
    dataset: banking77
    field: labels
```

BANKING77 exposes its label space in `DatasetLoadResult.metadata`.

`resolve_capability_context` resolves the binding generically and produces the
`TaskExecutionContext.metadata` consumed by the calibrated classification task.

The same mechanism can later provide other cross-dataset or literal task context without
changing the central runner.

## QA + abstention

A repository-authored controlled corpus contains both answerable and unanswerable
questions.

The task requires structured output:

```json
{"answer": "...", "abstain": false}
```

Metrics:

- exact match on answerable questions;
- answerability/abstention accuracy;
- parse validity.

For unanswerable cases, exact-match is recorded as non-applicable rather than pretending
that an empty string is a semantic answer.

## Mathematical reasoning

The initial controlled reasoning corpus contains arithmetic, percentage, rate and simple
geometry problems.

The model is asked for a structured **final answer only**.

The benchmark evaluates:

- normalized final-answer accuracy;
- parse validity;
- latency/tokens/cost at suite level.

Private chain-of-thought is neither requested nor scored.

## Controlled dataset adapter

MCB-6 adds `ControlledYamlDataset`, a reusable repository-backed adapter for small,
versioned controlled corpora.

It supports generic:

- input;
- expected value;
- metadata;
- deterministic profile sampling;
- source-file checksum;
- selection fingerprint.

QA and mathematical reasoning use this adapter rather than introducing one Python loader
per controlled dataset.

## Capability matrix planning

`CapabilitySuiteBundle` composes:

```text
models.yaml
tasks.yaml
datasets.yaml
profiles.yaml
suite.yaml
    |
    v
validated suite bundle
    |
    v
model x capability x dataset matrix
```

`plan_matrix` validates model capabilities and returns neutral matrix arms containing:

- model;
- capability;
- task;
- dataset;
- runtime;
- provider.

It does not perform inference. MCB-7 consumes this exact matrix plan.

## Inspection CLI

The suite can be validated and expanded without provider credentials:

```bash
uv run python scripts/suite_inspect.py \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities all
```

This proves that local and API model definitions traverse the same model/task/dataset
composition path.

Actual multi-model execution remains MCB-7.

## Definition of Done

- [x] suite contract and strict loader exist;
- [x] suite references are validated against task/dataset/profile registries;
- [x] capability context bindings are typed and generic;
- [x] five capabilities are declared;
- [x] at least three independent task/dataset families are present;
- [x] BANKING77 classification is in the generic suite;
- [x] OOS/calibration composes BANKING77 + CLINC150 without dataset coupling;
- [x] structured output is in the generic suite;
- [x] QA + abstention has a versioned controlled corpus/task;
- [x] mathematical reasoning has a versioned controlled corpus/task;
- [x] private chain-of-thought is not scored;
- [x] one command can plan multiple models across multiple capabilities;
- [ ] focused MCB-6 CI passes;
- [ ] previous MCB/VLM/image-generation gates remain green;
- [ ] full Jev characterization suite remains green.

The original plan phrase "same command can evaluate multiple models on multiple tasks" is
completed operationally by MCB-7, because inference execution is explicitly the unified
runner's responsibility. MCB-6 completes the declarative composition and matrix planning
boundary required by that runner.
