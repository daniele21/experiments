# Jev vs LLM — decision benchmark

A reproducible benchmark for understanding **where a System One decision model such as Jev differs from a general-purpose LLM**. The goal is not to produce a single winner. The suite measures which architecture is a better fit for different kinds of decision workloads.

> **Publication constraint:** TypeSafe's current Master Customer Agreement contains restrictions around publishing benchmark/performance information. Keep Jev numeric results private unless the terms applicable to your account permit publication or TypeSafe authorizes it. Raw benchmark outputs are gitignored by default.

## What is being compared

The benchmark starts with two executable providers:

- **Jev workflow** — typed `Choice`, `Score`, and `Noul` questions sent to `jev-latest` (or an explicitly pinned Jev model).
- **LLM workflow** — the same decomposed questions sent to an explicitly configured OpenAI model using strict Structured Outputs.

A third baseline, **LLM monolithic**, is planned for workflow experiments. It will ask the LLM for only the final action so we can separate the benefit of workflow decomposition from the benefit of the underlying model architecture.

LLM confidence values are self-reported. They are deliberately measured, but must not be assumed to mean the same thing as Jev confidence before calibration is evaluated empirically.

## Experiments

| ID | Experiment | Primary question | Main metrics |
|---|---|---|---|
| 01 | Routing | Can the model map short requests to a fixed category? | accuracy, valid-output rate, p50/p95 latency |
| 02 | Calibration | Does reported confidence correspond to observed correctness? | ECE, Brier score, reliability curve, accuracy-vs-coverage |
| 03 | Parallel scaling | What happens when one state needs 1→32 independent judgments? | p50/p95 latency, latency/question, token usage |
| 04 | Deterministic workflow | How well do fuzzy judgments compose with explicit Python rules? | intermediate accuracy, final-action accuracy, latency |
| 05 | Hybrid agent | Can decision primitives handle routing while an LLM remains available for generation? | final-action accuracy, decision latency, calls/tokens |

The included datasets are deliberately small **smoke datasets** so the harness is runnable immediately. They are not sufficient for publishable conclusions. The next step is to add larger public or independently labelled datasets while keeping the same runner and report format.

## Fairness rules

1. Pin the exact model versions used in a benchmark run.
2. Run providers from the same machine/region and record network conditions.
3. Warm up before timed runs and use repeated samples for latency.
4. Give Jev and the workflow LLM the same state and semantically equivalent questions.
5. Keep deterministic calculations and business rules in code, not in either model.
6. Report p50 and p95, not a single best latency.
7. Separate provider errors/schema errors from semantic wrong answers.
8. Do not interpret LLM self-reported confidence as calibrated until the reliability experiment supports that conclusion.

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

Run each provider separately so rate limits or temporary provider issues do not contaminate the other run:

```bash
uv run jev-bench run --provider jev --scaling-repeats 10
uv run jev-bench run --provider llm --scaling-repeats 10
uv run jev-bench report
```

Open:

```text
results/report.html
```

The report is the primary human-facing artifact. It contains KPI cards plus interactive charts for accuracy, latency, accuracy-vs-latency, calibration and parallel scaling.

## Result schema

Every raw row includes:

```text
experiment, case_id, provider, model, question_id,
expected, actual, correct, confidence,
latency_ms, input_tokens, output_tokens,
valid, error
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
- [ ] Larger independently labelled datasets
- [ ] LLM-monolithic baseline for experiments 04/05
- [ ] Accuracy-vs-coverage threshold chart
- [ ] Optional cost normalization from a run manifest
- [ ] Run manifest: git SHA, region, timestamp, package/model versions

## Sources used for the design

The implementation follows TypeSafe's current public API shape: a shared `state`, typed questions (`Choice`, `Score`, `Noul`), and multiple independent questions in one `system_one` call. See the TypeSafe Quick Start, Primitives, and Confidence documentation. The OpenAI baseline uses strict JSON-schema Structured Outputs through the Responses API.
