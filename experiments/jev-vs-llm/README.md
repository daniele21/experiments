# Jev vs LLM — decision benchmark

A reproducible benchmark for comparing **bounded decision systems** across different model architectures:

- **Jev / System One** for typed probabilistic decisions;
- **OpenAI GPT workflow models** for the same decomposed decisions;
- **OpenAI GPT monolithic baselines** for workflow/agent final actions;
- **Korgis local LLMs** served through the same OpenAI-compatible HTTP boundary.

The goal is **not** to declare one universal winner. The benchmark is designed to answer a more useful question:

> For a specific decision workload, what quality, reliability, latency and provider cost do we get from each architecture?

The benchmark is intentionally inspectable. You can start from aggregate results and drill down to the exact request, question, expected answer, model answer, confidence, latency, token usage, API cost and error that produced the metric.

> **Publication constraint:** TypeSafe's current Master Customer Agreement can restrict publication of benchmark/performance information. Keep Jev numeric results private unless the terms applicable to the account permit publication or TypeSafe authorizes it. Raw benchmark outputs are gitignored by default.

---

## 1. What is compared

### Jev workflow

Jev receives typed bounded questions such as `Choice`, `Noul` and `Score`.

It is evaluated as a **decision model**, not as a text generator.

### GPT decomposed workflow

GPT receives the same state and semantically equivalent bounded questions.

The benchmark asks it to return a compact structured answer containing only:

- selected value;
- confidence;
- selected-answer probability.

It does **not** ask GPT to generate an entire 77-class probability distribution because that would artificially penalize an autoregressive model's output latency.

Default GPT matrix:

```text
gpt-5.6-luna
gpt-5.6-terra
gpt-5.6-sol
```

Override it with `OPENAI_MODELS` or `--models`.

### GPT monolithic baseline

For experiments 04 and 05, GPT can also receive the complete policy and return the final action directly.

This lets us separate two effects:

```text
better model architecture?
        vs
better workflow decomposition?
```

### Korgis local models

The local comparison runs through **Korgis / Local LLM Server**, not directly against llama.cpp.

Default local matrix:

| Korgis key | Model | Quantization | Provider API fee |
|---|---|---|---:|
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | $0 |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | $0 |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | $0 |

Qwen3.5 has official 4B and 9B checkpoints; the 9B model is used as the larger Qwen3.5 comparison.

Local provider API fee is recorded as zero. That **does not mean local inference has zero total cost**: electricity, device purchase/amortisation, thermal impact and device opportunity cost are currently outside the cost model.

See [`LOCAL_MODELS.md`](LOCAL_MODELS.md) for the local-runtime details.

---

## 2. The five experiments

| ID | Experiment | What it tests | Primary metrics |
|---|---|---|---|
| 01 | Routing | Fixed-category classification | accuracy, macro-F1, valid-output rate, latency |
| 02 | Calibration | Whether confidence/probability tracks correctness | ECE, Brier, reliability, accuracy-vs-coverage |
| 03 | Parallel scaling | 1 → 32 independent decisions in one request | validity, p50/p95 latency, tokens, cost |
| 04 | Deterministic workflow | Fuzzy model decisions + explicit Python rules | intermediate accuracy, final-action accuracy, validity |
| 05 | Hybrid agent | Decision layer for routing/escalation | intermediate accuracy, final-action accuracy, latency |

Detailed protocol notes live in [`experiments/`](experiments/).

### Which dataset does each experiment use?

There are two benchmark tiers.

#### Smoke tier

Small committed cases used for:

```text
01 Routing
02 Calibration
03 Scaling
04 Workflow
05 Agent
```

Use this tier when:

- developing the harness;
- testing a new provider/model;
- validating structured output;
- debugging errors;
- comparing workflow behavior;
- running local models cheaply.

#### Public tier

Public datasets are used only for the classification/calibration experiments:

```text
01 Routing     → BANKING77
02 Calibration → BANKING77 + filtered CLINC150 OOS
```

Experiments 03/04/05 currently use the committed controlled workloads, not public datasets.

See [`DATASETS.md`](DATASETS.md) for provenance and licensing.

---

## 3. Setup

From the repository root:

```bash
cd experiments/jev-vs-llm

cp .env.example .env
uv sync --extra dev
```

### Cloud providers

Set only the credentials you intend to use:

```bash
export TYPESAFE_API_KEY="..."
export JEV_MODEL="jev-<pinned-version>"

export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-terra"
export OPENAI_MODELS="gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol"

# Decision benchmarks should explicitly avoid unnecessary reasoning cost.
export OPENAI_REASONING_EFFORT="none"
```

For exploratory Jev runs, `jev-latest` can be used. For reproducible comparisons, pin the exact Jev version.

### Measurement context

Record where the benchmark runs:

```bash
export BENCHMARK_LOCATION="milan-local"
```

Transport defaults can also be controlled:

```bash
export BENCHMARK_MAX_RETRIES=0
export BENCHMARK_TIMEOUT_SECONDS=60
```

Retries are intentionally normalized because hidden retry behavior would distort both latency and error-rate comparisons.

---

## 4. Start Korgis for local models

First download the local GGUF files from the Korgis repository/environment:

```bash
local-llm download qwen3.5-4b-q4km
local-llm download qwen3.5-9b-q4km
local-llm download nemotron-nano-4b
```

For the default memory-bounded mode, start Korgis with the small anchor model and admin API enabled:

```bash
local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark defaults to:

```text
http://127.0.0.1:1235/v1
```

Override it if needed:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
```

Before spending time on a benchmark, verify the runtime:

```bash
curl http://127.0.0.1:1235/health
curl http://127.0.0.1:1235/v1/models
curl http://127.0.0.1:1235/v1/runtime/identity
```

The default local matrix is executed sequentially. Korgis activates one model, benchmarks it, returns to the anchor model and unloads the temporary model so all GGUF weights do not need to remain resident simultaneously.

Runtime identity is captured in the run manifest, including model/runtime information exposed by Korgis.

---

## 5. Recommended testing workflow

A good benchmark sequence is:

```text
1. Validate one model / one experiment
             ↓
2. Run the smoke suite locally
             ↓
3. Run public budget profile
             ↓
4. Inspect granular failures
             ↓
5. Increase sample size only if needed
             ↓
6. Run cloud + local comparison
```

This avoids spending API budget before the harness and local models are known to work.

### Step 1 — run one experiment

The `experiment` command is the fastest way to iterate.

#### Local routing

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

#### Public BANKING77 routing only

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model qwen3.5-4b-q4km \
  --dataset public \
  --profile budget
```

#### Calibration only

```bash
uv run jev-bench experiment calibration \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

#### Scaling only

```bash
uv run jev-bench experiment scaling \
  --provider korgis \
  --model qwen3.5-4b-q4km \
  --scaling-repeats 10
```

#### Workflow only

```bash
uv run jev-bench experiment workflow \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

#### Agent only

```bash
uv run jev-bench experiment agent \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

The same command works with Jev:

```bash
uv run jev-bench experiment routing --provider jev
```

and GPT:

```bash
uv run jev-bench experiment routing \
  --provider llm \
  --model gpt-5.6-terra
```

For the monolithic GPT baseline:

```bash
uv run jev-bench experiment workflow \
  --provider llm-monolithic \
  --model gpt-5.6-terra
```

`llm-monolithic` is available only for `workflow` and `agent`.

### Step 2 — run all three local models

This uses no Jev/OpenAI inference:

```bash
uv run jev-bench compare-local --profile budget
```

Default local matrix:

```text
Qwen3.5-4B Q4_K_M
Qwen3.5-9B Q4_K_M
Nemotron Nano 4B Q4_K_M
```

Outputs:

```text
results/local_report.html
results/raw/local_results.csv
results/manifests/<run-group>.json
```

### Step 3 — prepare public data

```bash
uv run jev-bench prepare-data
```

Canonical dataset files are downloaded into the local gitignored cache.

### Step 4 — choose a public profile

| Profile | BANKING77 routing | Calibration in-scope | CLINC150 OOS | Use when |
|---|---:|---:|---:|---|
| `budget` | 77 | 40 | 40 | first real comparison / constrained API budget |
| `quick` | 154 | 100 | 100 | second-pass directional evidence |
| `standard` | 770 | 500 | 500 | stronger benchmark evidence |
| `full` | all 3,080 | matched to all filtered OOS | all filtered OOS | expensive / final high-sample run |

Start with `budget`. Do not jump to `standard` or `full` before checking actual token usage and cost from a smaller run.

### Step 5 — compare Jev + GPT

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol
```

For reproducible public runs, `JEV_MODEL` must be pinned unless the moving-model override is explicitly enabled.

### Step 6 — compare cloud + local in one run group

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-local \
  --local-models qwen3.5-4b-q4km,qwen3.5-9b-q4km,nemotron-nano-4b
```

This is the preferred command when you want a direct public routing/calibration comparison under the same run group.

---

## 6. Smoke comparison across Jev and GPT

For the complete five-experiment committed smoke suite:

```bash
uv run jev-bench compare \
  --scaling-repeats 30 \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol
```

This includes:

```text
Routing
Calibration
Scaling
Workflow
Agent
```

and generates:

```text
results/report.html
```

Use the smoke suite for architectural behavior. Use the public tier for larger classification/calibration evidence.

---

## 7. What each command produces

Every benchmark run produces three forms of evidence.

### Raw rows

Examples:

```text
results/raw/results.csv
results/raw/public_results.csv
results/raw/local_results.csv
results/raw/experiment_results.csv
```

Raw rows are the source of truth for analysis.

### Manifest

```text
results/manifests/<run-group>.json
```

The manifest records:

- run group;
- suite/profile;
- UTC creation time;
- runner location;
- git commit;
- Python/platform;
- package versions;
- requested model IDs;
- resolved model IDs;
- dataset revisions;
- transport retry/timeout configuration;
- OpenAI reasoning effort;
- pricing snapshot;
- Korgis runtime identity when local models are used.

### HTML explorer

Examples:

```text
results/report.html
results/public_report.html
results/local_report.html
results/experiment_report.html
```

The HTML report is the primary human-facing artifact.

It is static: no backend, database or npm application is required.

---

## 8. How to read the report

Read the report from **aggregate → breakdown → case → decision**.

### Overview

Use Overview to answer:

```text
How accurate is each model?
How fast is it?
How much provider API cost does it generate?
Which experiment is driving that cost?
```

Main views:

- model KPI cards;
- accuracy vs latency;
- accuracy vs API cost;
- API cost by experiment.

Do not use Overview alone to decide whether a model is suitable. Drill into the experiment that matters.

### Routing

Routing exposes:

```text
aggregate accuracy / macro-F1
        ↓
per-class accuracy + valid rate
        ↓
confusion pairs
        ↓
individual requests
        ↓
individual model decision
```

Per-class breakdown shows:

- expected class;
- number of cases;
- valid-output rate;
- accuracy;
- most frequent wrong prediction.

Use this to find class collapse, systematic confusion and models that look acceptable only because some intents are easy.

### Calibration

Calibration distinguishes two concepts:

- `predicted_probability` → used for ECE/Brier;
- `confidence` → used for selective automation / abstention.

The report shows:

- reliability diagram;
- ECE;
- Brier score;
- confidence-vs-coverage curve;
- in-scope vs OOS behavior;
- individual predictions.

A model that is accurate but badly calibrated may still be risky for autonomous decision-making.

Example:

```text
confidence = 0.95
actual correctness = 0.55
```

means the model is strongly overconfident.

### Parallel scaling

Scaling sends:

```text
1
2
4
8
16
32
```

independent questions in one request.

Inspect:

- valid-output rate;
- p50/p95 latency;
- tokens;
- API cost;
- exact schema/JSON errors;
- every individual scaling request.

For small local models this experiment is especially important: a model can perform acceptably on one decision but stop reliably respecting structured output at 8/16/32 decisions.

### Deterministic workflow

The workflow report shows both **intermediate model judgments** and the **final deterministic action**.

A case can be inspected as:

```text
original input
    ↓
receipt_readable       expected / actual
category               expected / actual
description_matches    expected / actual
fraud_pattern          expected / actual
    ↓
Python business rule
    ↓
final expected / actual action
```

This makes it possible to understand whether failure came from:

- the model's fuzzy judgment;
- a specific intermediate decision;
- the deterministic rule composition;
- invalid/missing structured output.

### Hybrid agent

The agent experiment exposes the same trace structure for:

```text
intent
urgent
human_requested
angry
    ↓
deterministic routing
    ↓
answer / refund_flow / cancel_flow / priority_support / handoff
```

Use the intermediate trace rather than only final-action accuracy.

### Error explorer

Each experiment keeps operational/format failures separate from semantic mistakes.

Examples:

```text
invalid JSON
missing answer
unexpected question id
out-of-domain choice
provider error
timeout
```

A wrong but valid prediction is a **quality error**.

An invalid response is a **reliability/protocol error**.

Do not merge those two failure modes.

---

## 9. Case-level drill-down

Every searchable case card can expose:

```text
input_state
case_id
model
expected
actual
correct
confidence
predicted_probability
valid
error
latency_ms
input_tokens
output_tokens
estimated_cost_usd
decision_trace
```

Use the search box to find:

- a case ID;
- a specific input phrase;
- an expected/actual class;
- `handoff`, `refund`, etc.;
- an error such as `invalid JSON`.

Global model chips also filter the granular case views and tables.

---

## 10. How to compare models correctly

### Do not use a single universal score

These systems have different strengths. Compare them on the requirement that matters for the workload.

### First check validity

Before accuracy:

```text
valid-output rate
```

If a model returns valid structured output only 80% of the time, an 85% accuracy measured only on valid requests can be misleading.

Always read:

```text
validity
+
accuracy among valid outputs
+
raw invalid/error cases
```

### Then compare quality

For routing:

```text
accuracy
macro-F1
per-class behavior
confusion pairs
```

For workflow/agent:

```text
intermediate accuracy
final-action accuracy
individual traces
```

### Then compare latency

Use:

```text
p50
p95
p99
```

not a single fastest request.

Remember:

- cloud latency includes network/provider time;
- local latency includes the Korgis HTTP boundary;
- Korgis model startup/switching is excluded from per-request latency;
- comparisons should be made from the same machine/location whenever possible.

### Then compare cost

Cloud cost is estimated from provider-reported token usage and the dated `pricing_snapshot.json`.

The report includes:

```text
API cost / request
API cost / 1,000 requests
run cost
cost by experiment
```

For Korgis:

```text
provider API fee = $0
```

but hardware/energy/TCO is unmeasured.

### Finally inspect calibration

Do not assume:

```text
Jev confidence
GPT confidence
local-LLM confidence
```

have the same semantics.

Calibration is measured empirically.

---

## 11. Fair-comparison rules

For a benchmark intended to support real architectural conclusions:

1. Pin exact model versions.
2. Use the same labelled cases for every model being directly compared.
3. Keep provider order and measurement location documented.
4. Give decomposed generative baselines semantically equivalent questions.
5. Keep deterministic business logic in Python.
6. Do not repair invalid model outputs into correct answers.
7. Keep schema/provider failures separate from semantic errors.
8. Use p50/p95/p99 latency.
9. Keep confidence separate from selected-answer probability.
10. Normalize retry/timeout behavior.
11. Record Korgis runtime identity for local models.
12. Use the pricing snapshot associated with that run; never retroactively apply a newer list price to an old benchmark.
13. Treat local `$0` as zero provider fee, not zero TCO.
14. Do not compare unlike experiment metrics by averaging them into one global winner.

---

## 12. Cost-conscious testing

If API budget matters, use this order:

```text
local-only smoke
      ↓
single experiment
      ↓
public budget
      ↓
inspect actual $/request
      ↓
quick / standard only if justified
```

For OpenAI decision benchmarks, keep:

```bash
export OPENAI_REASONING_EFFORT="none"
```

unless reasoning effort itself is the variable being tested.

The `budget` profile is specifically intended for the first real cloud comparison.

---

## 13. Result schema

Every raw row can include:

```text
run_id
run_group
suite
run_timestamp_utc
runner_location

experiment
case_id
input_state

provider
model
question_id

expected
actual
decision_trace
correct

confidence
predicted_probability

primary_metric

latency_ms
input_tokens
cached_input_tokens
output_tokens
estimated_cost_usd

valid
error
```

Experiment-specific metadata such as `difficulty`, dataset revision and `question_count` may also be present.

The raw schema is intentionally simple enough to analyze with pandas, DuckDB, BigQuery or another reporting layer.

---

## 14. Architecture

```text
                     benchmark cases
                           │
          ┌────────────────┼──────────────────┐
          │                │                  │
          ▼                ▼                  ▼
    JevProvider      OpenAIProvider      KorgisProvider
          │                │                  │
          │                │             Korgis HTTP
          │                │                  │
          │                │             local GGUF
          └────────────────┼──────────────────┘
                           ▼
                      common rows
                           │
                           ▼
                       metrics.py
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          raw CSV       manifest     report.py
                                         │
                                         ▼
                              static HTML explorer
                                         │
                    aggregate → case → decision/error
```

---

## 15. Quick command reference

### Setup

```bash
cd experiments/jev-vs-llm
uv sync --extra dev
```

### Public datasets

```bash
uv run jev-bench prepare-data
```

### One local experiment

```bash
uv run jev-bench experiment routing \
  --provider korgis \
  --model qwen3.5-4b-q4km
```

### One GPT experiment

```bash
uv run jev-bench experiment routing \
  --provider llm \
  --model gpt-5.6-terra
```

### All local public routing/calibration

```bash
uv run jev-bench compare-local --profile budget
```

### Jev + GPT public comparison

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol
```

### Jev + GPT + Korgis

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-local
```

### Regenerate a report from existing raw rows

```bash
uv run jev-bench report \
  --input-csv results/raw/results.csv \
  --output-html results/report.html
```

---

## 16. Current implementation status

- [x] Common question/result model
- [x] Jev provider using `typesafe-sdk`
- [x] OpenAI structured-output workflow baseline
- [x] GPT monolithic workflow/agent baseline
- [x] Korgis OpenAI-compatible local provider
- [x] Qwen3.5-4B Q4_K_M local baseline
- [x] Qwen3.5-9B Q4_K_M local baseline
- [x] Nemotron Nano 4B Q4_K_M local baseline
- [x] Experiment 01 — routing
- [x] Experiment 02 — calibration
- [x] Experiment 03 — 1/2/4/8/16/32 parallel scaling
- [x] Experiment 04 — deterministic expense workflow
- [x] Experiment 05 — hybrid support-agent decision layer
- [x] Single-experiment CLI
- [x] Public BANKING77 + CLINC150 benchmark tier
- [x] Budget/quick/standard/full profiles
- [x] Raw result persistence
- [x] Case input persistence
- [x] Workflow/agent decision traces
- [x] Accuracy-vs-coverage analysis
- [x] Cost tracking from a dated provider pricing snapshot
- [x] Cost by request / 1,000 requests / run / experiment
- [x] Interactive static HTML explorer
- [x] Per-class routing breakdown
- [x] Searchable case-level drill-down
- [x] Question/decision-level drill-down
- [x] Error explorer
- [x] Run grouping and runner location
- [x] Manifest with git SHA, model IDs, dataset revisions, package/runtime versions, transport and pricing
- [x] Korgis runtime identity snapshot

---

## 17. Related documentation

- [`METHODOLOGY.md`](METHODOLOGY.md) — benchmark design, fairness and statistical protocol.
- [`DATASETS.md`](DATASETS.md) — public dataset provenance and profiles.
- [`LOCAL_MODELS.md`](LOCAL_MODELS.md) — Korgis/local-model setup and runtime semantics.
- [`experiments/`](experiments/) — protocol and interpretation notes for experiments 01–05.

