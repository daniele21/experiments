# Jev vs LLM — decision benchmark

A reproducible benchmark for understanding **where a System One decision model such as Jev differs from a general-purpose LLM**. The goal is not to produce a single winner. The suite measures which architecture is a better fit for different kinds of decision workloads.

> **Publication constraint:** TypeSafe's current Master Customer Agreement contains restrictions around publishing benchmark/performance information. Keep Jev numeric results private unless the terms applicable to your account permit publication or TypeSafe authorizes it. Raw benchmark outputs are gitignored by default.

## What is being compared

The benchmark has three executable arms:

- **Jev workflow** — typed `Choice`, `Score`, and `Noul` questions sent to `jev-latest` (or an explicitly pinned Jev model).
- **LLM workflow** — the same decomposed questions sent to an explicitly configured OpenAI model using strict Structured Outputs.
- **LLM monolithic** — for workflow experiments 04/05, the complete policy is given to the LLM and it returns the final action directly. This separates the benefit of decomposition from the benefit of the model architecture.

LLM confidence values are self-reported. They are deliberately measured, but must not be assumed to mean the same thing as Jev confidence before calibration is evaluated empirically.

## Experiments

| ID | Experiment | Primary question | Main metrics |
|---|---|---|---|
| 01 | Routing | Can the model map short requests to a fixed category? | accuracy, valid-output rate, p50/p95 latency |
| 02 | Calibration | Does reported confidence correspond to observed correctness? | ECE, Brier score, reliability curve, accuracy-vs-coverage |
| 03 | Parallel scaling | What happens when one state needs 1→32 independent judgments? | p50/p95 latency, latency/question, token usage |
| 04 | Deterministic workflow | How well do fuzzy judgments compose with explicit Python rules? | intermediate accuracy, final-action accuracy, latency |
| 05 | Hybrid agent | Can decision primitives handle routing while an LLM remains available for generation? | final-action accuracy, decision latency, calls/tokens |

The repo contains both small committed **smoke datasets** and a larger **public benchmark tier**. The public tier downloads BANKING77 for 77-class intent classification and CLINC150 out-of-scope examples for calibration/OOD evaluation. See [`DATASETS.md`](DATASETS.md) for provenance, licensing notes and profiles.

## Fairness rules

1. Pin the exact model versions used in a benchmark run.
2. Run providers from the same machine/region and record network conditions.
3. Warm up before timed runs and use repeated samples for latency.
4. Give Jev and the workflow LLM the same state and semantically equivalent questions.
5. Keep deterministic calculations and business rules in code, not in either model.
6. Report p50, p95 and p99, not a single best latency.
7. Separate provider errors/schema errors from semantic wrong answers.
8. Keep `predicted_probability` separate from provider-native `confidence`: ECE/Brier use probability assigned to the selected class; selective automation uses native confidence.
9. Normalize SDK retries/timeouts across providers so latency and error-rate comparisons have the same transport policy.

## Setup

```bash
cd experiments/jev-vs-llm
cp .env.example .env
uv sync --extra dev
```

Export the required keys and choose the exact LLM model:

```bash
export TYPESAFE_API_KEY="..."
export OPENAI_API_KEY="..."
export OPENAI_MODEL="<exact model id>"
```

`JEV_MODEL` defaults to `jev-latest` for exploration. For a benchmark that must remain reproducible, set it to the exact returned Jev model version.

## Run

### Smoke suite

```bash
export BENCHMARK_LOCATION="milan-local"
uv run jev-bench compare --scaling-repeats 30
```

This generates `results/report.html`.

### Public classification + calibration benchmark

Download/cache the canonical datasets:

```bash
uv run jev-bench prepare-data
```

Run the standard profile:

```bash
uv run jev-bench compare-public --profile standard
```

Profiles:

| Profile | BANKING77 routing | Calibration in-scope | CLINC150 OOS |
|---|---:|---:|---:|
| `quick` | 154 (~2/intent) | 100 | 100 |
| `standard` | 770 (~10/intent) | 500 | 500 |
| `full` | all 3,080 test cases | matched to all filtered OOS | all filtered OOS |

The public benchmark generates `results/public_report.html`.

The HTML report is the primary human-facing artifact. It shows accuracy and macro-F1 with 95% confidence intervals, latency, accuracy-vs-latency, probability calibration, confidence-based coverage, in-scope vs OOS performance, top confusion pairs, and parallel scaling when present.

## Result schema

Every raw row includes:

```text
run_id, run_group, suite, run_timestamp_utc, runner_location,
experiment, case_id, provider, model, question_id,
expected, actual, correct, confidence, predicted_probability,
primary_metric, latency_ms, input_tokens, output_tokens, valid, error
```

This deliberately keeps the raw representation simple enough to analyze with pandas, DuckDB, BigQuery, or another reporting layer later.

## Architecture

```text
cases / states
     │
     ├───────────────┐
     ▼               ▼
 JevProvider     OpenAIProvider
     │               │
 typed answers   structured answers
     └───────┬───────┘
             ▼
       common rows
             │
       metrics.py
             │
             ▼
   results/raw/results.csv
             │
         report.py
             │
             ▼
     results/report.html
```

See [`METHODOLOGY.md`](METHODOLOGY.md) for benchmark-grade sample sizes, latency protocol, hypotheses and dataset rules.

## Current implementation status

- [x] Common question/result model
- [x] Jev provider using `typesafe-sdk`
- [x] OpenAI Structured Outputs workflow baseline
- [x] Experiment 01 — routing
- [x] Experiment 02 — calibration harness
- [x] Experiment 03 — 1/2/4/8/16/32 question scaling
- [x] Experiment 04 — expense decision workflow
- [x] Experiment 05 — support decision/hybrid-agent core
- [x] Interactive HTML dashboard
- [x] Raw result persistence
- [x] Public benchmark tier: BANKING77 + CLINC150 OOS
- [x] LLM-monolithic baseline for experiments 04/05
- [x] Accuracy-vs-coverage threshold chart
- [x] Run grouping with UTC timestamp and runner location
- [ ] Optional cost normalization from dated price assumptions
- [ ] Full manifest: git SHA and installed package versions

## Sources used for the design

The implementation follows TypeSafe's current public API shape: a shared `state`, typed questions (`Choice`, `Score`, `Noul`), and multiple independent questions in one `system_one` call. See the TypeSafe Quick Start, Primitives, and Confidence documentation. The OpenAI baseline uses strict JSON-schema Structured Outputs through the Responses API.
