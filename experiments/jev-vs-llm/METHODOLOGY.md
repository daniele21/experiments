# Benchmark methodology

This document defines the benchmark protocol. The small datasets committed with the code are smoke tests for the harness; benchmark-grade conclusions require the larger sample sizes below.

## Benchmark arms

1. **Jev workflow** — independent typed questions (`Choice`, `Noul`, `Score`) evaluated against one shared state, then deterministic code combines answers.
2. **LLM workflow** — semantically equivalent decomposed questions, returned through strict Structured Outputs, then the same deterministic code combines answers.
3. **LLM monolithic** — for experiments 04/05 only, the whole policy is supplied to the LLM and it chooses the final action directly.

The third arm is essential: it separates the gain from **workflow decomposition** from the gain attributable to the **decision-model architecture**.

## Primary metrics

- **Accuracy**: exact final outcome for Choice/final actions; Noul values are thresholded at 0.5; Score tolerance is ±0.5 level.
- **Valid-output rate**: request returned all required answers and values stayed inside the expected contract.
- **Latency**: wall-clock client-observed end-to-end latency. Report p50, p95 and p99.
- **Probability calibration**: Expected Calibration Error plus Brier score computed on the probability assigned to the selected class.
- **Selective automation**: accuracy vs coverage while increasing the provider-native confidence threshold.
- **Scaling**: latency as independent questions in one request increase 1, 2, 4, 8, 16, 32.
- **Token usage**: input/output tokens when exposed by the provider. Cost normalization is optional and must use dated price assumptions.

For workflow experiments, **primary accuracy means final-action accuracy**. Intermediate question accuracy is reported separately so a workflow with four subquestions is not accidentally weighted four times more heavily than a single final outcome.

## Latency protocol

For benchmark-grade runs:

1. Run all providers from the same host and region.
2. Record the runner location with `BENCHMARK_LOCATION`.
3. Pin exact model IDs; do not publish a comparison using moving `latest` aliases.
4. Perform 5 untimed warm-up requests per provider/shape.
5. Run at least 30 measured repeats for each scaling point.
6. Execute the providers sequentially for the default latency benchmark; a separate throughput benchmark can test concurrency later.
7. Report failed requests; do not silently remove them.
8. The harness normalizes both provider SDKs with `BENCHMARK_MAX_RETRIES=0` by default and the same request timeout. This measures single-attempt latency and exposes provider errors instead of hiding them behind retries. Change these settings only as an explicit separate experiment.

Client-observed latency includes network distance. That is intentional for user-experience measurements, but infrastructure/model latency should be measured separately when provider-side timing becomes available.

## Experiment 01 — routing / fixed classification

**Hypothesis:** typed decision models should be competitive on bounded classification while avoiding free-form output failure modes.

Public benchmark: BANKING77 official test split, 77 intents. The `standard` profile samples ~10 examples per intent; the `full` profile runs all 3,080 official test examples.

Report: accuracy, macro-F1 (planned when the larger dataset lands), valid-output rate, p50/p95/p99 latency.

## Experiment 02 — calibration / abstention

**Hypothesis:** useful automation depends not only on being right but on knowing when not to act.

Public benchmark: a balanced mixture of BANKING77 in-scope test examples and conservatively filtered CLINC150 `oos_test` examples mapped to an explicit `other` choice. The `full` profile uses all filtered OOS examples and matches them with the same number of BANKING77 cases. This directly tests both classification quality and rejection/OOD behavior without asking a tested model to create the labels.

Report: reliability curve, ECE and Brier score on selected-class probability, plus accuracy-vs-coverage using native confidence. The key operational question is: *at 95% required accuracy, what share of cases can each system automate?*

LLM confidence in this suite is self-reported. Jev confidence and LLM confidence are therefore treated as provider-native abstention scores, not as probabilities. Probability calibration uses the probability assigned to the selected class instead.

## Experiment 03 — parallel decision scaling

**Hypothesis:** Jev's parallel sampler should make the marginal latency of additional independent judgments substantially smaller than autoregressive structured generation.

Use exactly the same state while increasing the number of independent questions: 1 → 2 → 4 → 8 → 16 → 32. Use ≥30 repeats after warm-up for each point.

Report: median/p95 latency by question count, latency growth relative to one question, tokens/request, and eventually throughput under controlled concurrency.

## Experiment 04 — deterministic business workflow

**Hypothesis:** decomposing fuzzy judgments and keeping policy/rules in code improves reliability and makes changes auditable.

The initial smoke workflow is expense approval. Benchmark-grade target: ≥300 cases spanning readable/unreadable evidence, categories, amount thresholds, mismatches and fraud/tampering cases. Ground truth should come from the structured case generator or independent human labels, never from the tested model itself.

Compare final-action accuracy among Jev workflow, LLM workflow and LLM monolithic. Also report intermediate-question accuracy for diagnostic purposes.

## Experiment 05 — hybrid agent decision layer

**Hypothesis:** an architecture where a decision model handles routing/guardrails and an LLM handles language generation can reduce decision latency without sacrificing task success.

The initial smoke implementation benchmarks the decision layer only. The next extension adds a generation step after the selected action and measures total task latency, LLM calls, tokens and final task success.

Benchmark-grade target: ≥300 support turns with multiple intents, escalation requests, urgency, frustration and policy edge cases.

## Dataset policy

- Committed smoke data is intentionally small and human-readable.
- Public benchmark data is downloaded into `data/cache/` and is not committed.
- Larger public datasets must preserve their original license and provenance.
- Synthetic benchmark cases must have deterministic or independently reviewed ground truth.
- Never use the tested model to create the sole reference label for the same benchmark.

## Reproducibility

Every row is tagged with a `run_id`, shared `run_group`, UTC timestamp and `runner_location`. A comparison should be executed with:

```bash
uv run jev-bench compare --scaling-repeats 30
```

The command runs all benchmark arms under one `run_group` and generates `results/report.html` for that exact group.

## Publication

Before publishing Jev numeric benchmark results, verify the TypeSafe terms applicable to the account used for the run. The repository therefore gitignores raw result directories by default; methodology and code can remain public independently of private numeric outputs.
