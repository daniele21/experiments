# MCB-10 — Vertical Benchmark Hardening & Efficiency

## 1. Objective

MCB-10 turns the generic capability benchmark into a compact, task-vertical
comparison system for local/open-weight and API/closed models.

The goal is decision-grade comparison under explicit runtime and API-cost constraints:

- compare the same fixed cases across models;
- spend cases on failure-mode coverage rather than raw volume;
- keep the default core suite comfortably below one hour on target local hardware when the pilot estimate fits the guardrail;
- keep API spend bounded and visible before the full run;
- preserve exact per-case evidence and neutral task-level reporting.

There is no mandatory overall score.

## 2. Core profile

| Capability | Core cases | Selection |
| --- | ---: | --- |
| intent classification | 154 | class-balanced BANKING77 |
| OOS / calibration | 154 | 77 in-scope + 77 OOS |
| structured output | 60 | 10 cases × 6 failure families |
| QA / abstention | 60 | 10 cases × 6 failure families |
| mathematical reasoning | 40 | stratified across 6 families |
| **Total / model** | **468** | same cases for every compared model |

Configured aggregate core guardrails:

- local target: 1,680 s / 28 min;
- local hard ceiling: 2,700 s / 45 min;
- API target: USD 0.45 / model;
- API hard ceiling: USD 1.00 / model.

These are benchmark design budgets, not promises about a model. Use the pilot estimator before a real run.

## 3. Profiles

MCB-10 introduces three benchmark tiers while retaining legacy aliases:

- smoke: development and CI-sized coverage;
- core: normal model comparison;
- extended: deeper public-dataset coverage or future extension cases;
- budget / standard: retained for backward compatibility;
- full: uncapped legacy profile.

A tier is capability-specific. Core therefore does not mean the same sample count for every task.

## 4. Capability-specific benchmark contract

CapabilitySpec now supports:

- benchmark tiers;
- dataset-specific case limits;
- deterministic selection strategy;
- stratified quotas;
- local runtime target/hard budgets;
- API cost target/hard budgets;
- paired comparison metric;
- practical-difference threshold.

The declaration lives in suite.yaml; the matrix runner contains no capability-specific branching.

## 5. Deterministic vertical selection

Controlled datasets carry case metadata:

- family;
- difficulty;
- challenge_type.

The v2 datasets are explicitly marked human_reviewed=false and their authored difficulty labels are provisional. Family coverage is structural; difficulty should be recalibrated after real-model item statistics and human review.

Supported selection strategies:

- profile: legacy seeded selection;
- fixed: stable source-order subset;
- stratified: deterministic quotas matched against sample metadata.

The selection fingerprint remains part of semantic case identity. The runner cache is capability/profile/seed-aware so two capabilities cannot accidentally reuse incompatible selections of the same dataset.

## 6. Controlled datasets v2

### Structured output — 60 cases

Families: flat, nested, arrays, optional/missing, noisy/stale information, adversarial/instruction-like data.

The primary metric is exact_match, which requires schema-valid output, every expected field value to match, and no unsupported/hallucinated field.

schema_valid_rate, field_accuracy and hallucinated_fields remain diagnostic metrics. Syntactically valid but semantically wrong JSON therefore does not receive full quality credit.

### QA + abstention — 60 cases

Families: direct, distractor, missing, near-answer, contradiction, multi-hop.

The primary metric is qa_correct:

- answerable case: correct non-abstained answer;
- unanswerable case: correct abstention.

exact_match, answerability_accuracy and parse_valid remain secondary.

### Mathematical reasoning — 40 cases

Families: arithmetic, percentages, multi-step, algebra, logic, constraints.

Only observable final answers are scored. Private chain-of-thought is never required or evaluated.

## 7. OOS / calibration semantics

The calibration task asks the model for a self-reported top-label confidence. ECE/Brier therefore describe calibration of that reported confidence, not hidden token-level model probabilities.

The paired comparison metric for this capability is oos_correct, matching the aggregate OOS-detection semantics.

## 8. Pre-run planning

Use:

~~~bash
uv run model-bench plan \
  --profile core \
  --capabilities all
~~~

This performs no inference and reports cases, selection strategy, practical delta, comparison metric, local time budgets and API cost budgets.

## 9. Pilot estimation

Before committing to the full core run:

~~~bash
uv run model-bench estimate \
  --models qwen3.5-2b-q4km \
  --profile core \
  --capabilities all \
  --pilot-cases 5
~~~

The pilot loads the exact same tier subsets as the full runner, chooses a deterministic representative slice, measures model preparation and request latency, projects mean/p95 runtime onto the planned case count, projects cost only when cost is actually known, checks the configured hard guardrail, and releases the runtime/model.

API cost stays null when neither the provider nor the versioned benchmark pricing snapshot can provide it. The estimator never invents a price.

MCB owns an explicit dated `pricing_snapshot.json`. The same snapshot is used by both `estimate` and the full runner. Its checksum is written to the run manifest and its provenance metadata is written to `environment.json` and raw inference evidence whenever snapshot pricing is applied.

Unknown models remain unpriced. Local hardware, electricity, amortisation and opportunity cost remain separate from provider token pricing.

## 10. Paired statistics

Models are compared on the same sample IDs.

For binary task metrics the offline report computes:

- B minus A quality delta;
- deterministic paired-bootstrap 95% interval;
- both-correct count;
- A-only-correct count;
- B-only-correct count;
- both-wrong count;
- exact McNemar p-value;
- configured practical-difference threshold.

This is computed from persisted evidence and triggers no provider calls. It does not create a global winner/ranking.

Paired quality statistics use cases evaluable for both models. Pipeline/provider failures remain explicit failure counts rather than being silently reclassified as wrong answers; the paired table therefore always shows its paired sample count.

## 11. Vertical reporting

For controlled datasets the HTML report now follows:

~~~text
capability
  -> model metrics
  -> paired comparison
  -> family breakdown
  -> difficulty breakdown
  -> individual cases
  -> normalized/raw evidence
~~~

Family and difficulty are persisted in case metadata and remain available to offline report rebuilding.

## 12. Compatibility and versioning

MCB-10 is incremental:

- v1 controlled datasets remain registered;
- legacy budget and standard profiles remain available;
- capabilities without benchmark tiers fall back to dataset profiles;
- DatasetLoadContext preserves previous positional argument order;
- structured-output task/evaluator is v2;
- QA/abstention task/evaluator is v2;
- suite version is v2.

## 13. Automated tests authored

Coverage was added or updated for:

- benchmark-tier parsing/validation;
- v2 dataset cardinality and family coverage;
- deterministic vertical planning;
- aggregate core time/API budgets;
- unified-runner v2 smoke/core cardinalities;
- resume/retry with v2 case identities;
- paired bootstrap/McNemar comparison;
- pilot runtime/cost projection;
- snapshot-priced API cost plus unknown-model cost remaining unknown;
- semantic structured-output scoring;
- unanswerable QA contribution to primary quality;
- benchmark/comparison metadata in manifests;
- paired/family/difficulty report output.

These gates still need execution in a local checkout because this agent environment cannot resolve GitHub from the container, so repository-local uv tests cannot be run here.

## 14. Remaining enhancements

Not blockers for using the vertical core suite:

- dedicated repeated performance microbenchmark with warmups/repetitions;
- local RAM/VRAM, tokens/s and startup/switch telemetry;
- harder curated near-domain OOS v2 set beyond the current filtered CLINC slice;
- parity-vs-native serving mode for structured generation;
- broader capabilities such as tool calling, instruction following, coding and long context.

## 15. Recommended validation sequence

From experiments/model-capability-benchmark:

~~~bash
uv sync --extra dev
uv run ruff check ../../packages/benchmark-core/src ../../packages/benchmark-core/tests src tests
uv run python -m compileall -q ../../packages/benchmark-core/src src
uv run pytest ../../packages/benchmark-core/tests tests
~~~

Then:

~~~bash
uv run model-bench plan --profile core --capabilities all
~~~

Then run a pilot:

~~~bash
uv run model-bench estimate \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --profile core \
  --capabilities all \
  --pilot-cases 5
~~~

Only when the projection fits the intended guardrails should the full core matrix be executed.
