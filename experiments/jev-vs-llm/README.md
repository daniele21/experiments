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
| `minicpm3-4b-q4km` | MiniCPM3-4B | Q4_K_M | $0 |
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | $0 |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | $0 |

The 4B tier deliberately includes Qwen3.5-4B, MiniCPM3-4B and Nemotron Nano 4B so model-family effects can be compared at roughly similar scale. Qwen3.5-9B remains as the larger within-family reference.

Local provider API fee is recorded as zero. That **does not mean local inference has zero total cost**: electricity, device purchase/amortisation, thermal impact and device opportunity cost are currently outside the cost model.

See [`LOCAL_MODELS.md`](LOCAL_MODELS.md) for the local-runtime details.

> [!TIP]
> To evaluate local models autonomously one at a time with live progress bars:
> ```bash
> # Run all experiments on a selected model:
> uv run python scripts/run_local_matrix.py --models nemotron-nano-4b --experiments all --dataset smoke
> ```
> See [`LOCAL_MODELS.md`](LOCAL_MODELS.md#15-autonomous-multi-model-runner-run_local_matrixpy) for full options and public benchmark commands.

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

## 3. Environment setup

The benchmark and Korgis are two separate Python projects. Set up both before running local-model comparisons.

A convenient directory layout is:

```text
~/dev/
├── experiments/
└── korgis/
```

### 3.1 Clone and prepare the benchmark

```bash
mkdir -p ~/dev
cd ~/dev

git clone https://github.com/daniele21/experiments.git
cd experiments/experiments/jev-vs-llm

python3 -m pip install "uv==0.8.13"
uv sync --extra dev

cp .env.example .env
```

All benchmark commands below should be run from:

```text
experiments/experiments/jev-vs-llm
```

Verify the CLI:

```bash
uv run jev-bench --help
```

### 3.2 Clone and prepare Korgis

In a second checkout:

```bash
cd ~/dev

git clone https://github.com/daniele21/korgis.git
cd korgis

python3 -m pip install "uv==0.8.13"
uv sync --frozen --extra dev
```

Verify Korgis:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm --help
```

If `local-llm` is installed globally you can omit `uv run --frozen`. The documentation uses the explicit `uv run --frozen local-llm ...` form because it guarantees that the command comes from the checked-out Korgis environment.

### 3.3 Install the `llama-server` backend

The benchmark GGUF entries use Korgis' managed `llama_server` backend. Korgis therefore needs access to a compatible `llama-server` executable.

On macOS or Linux with Homebrew:

```bash
brew install llama.cpp
command -v llama-server
llama-server --version
```

If the binary is on `PATH`, Korgis can resolve it normally. You can also make the path explicit:

```bash
export LOCAL_LLM_SERVER_BIN="$(command -v llama-server)"
```

or pass it at startup:

```bash
uv run --frozen local-llm serve \
  --model <MODEL_KEY> \
  --llama-server-bin "$(command -v llama-server)" \
  --enable-admin-api \
  --no-download
```

On other platforms, install a current `llama.cpp` build using the official install instructions or prebuilt binaries, then point `LOCAL_LLM_SERVER_BIN` / `--llama-server-bin` at the executable.

The important distinction is:

```text
Korgis package        → control plane / lifecycle / API
llama-server binary   → GGUF inference runtime
GGUF file             → model weights
```

All three must be available for the managed `llama_server` path.

### 3.4 Cloud-provider environment

Set only the credentials you intend to use:

```bash
export TYPESAFE_API_KEY="..."
export JEV_MODEL="jev-<pinned-version>"

export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-terra"
export OPENAI_MODELS="gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol"

# Decision/classification benchmarks should not pay for unnecessary reasoning.
export OPENAI_REASONING_EFFORT="none"
```

For exploratory Jev runs, `jev-latest` can be used. For reproducible comparisons, pin the exact Jev version.

### 3.5 Measurement environment

Record where the benchmark runs:

```bash
export BENCHMARK_LOCATION="milan-local"
```

Normalize transport behavior:

```bash
export BENCHMARK_MAX_RETRIES=0
export BENCHMARK_TIMEOUT_SECONDS=60
```

Retries are intentionally normalized because hidden retry behavior would distort both latency and error-rate comparisons.

---

## 4. Prepare Korgis and local GGUF models

Local inference is served by Korgis. The benchmark never opens a GGUF directly.

The runtime path is:

```text
GGUF artifact
     ↓
Korgis registry key
     ↓
llama.cpp / llama-server runtime
     ↓
Korgis OpenAI-compatible API
     ↓
jev-bench
```

### 4.1 Check which models Korgis already knows

From the Korgis checkout:

```bash
cd ~/dev/korgis

uv run --frozen local-llm models
```

A model can be downloaded by key only when that key exists in the merged Korgis registry.

For example, if the output contains:

```text
qwen3.5-4b-q4km
minicpm3-4b-q4km
nemotron-nano-4b
qwen3.5-9b-q4km
```

you can use the normal Korgis download path.

### 4.2 Download a model that is already registered in Korgis

```bash
uv run --frozen local-llm download qwen3.5-4b-q4km
uv run --frozen local-llm download minicpm3-4b-q4km
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm download qwen3.5-9b-q4km
```

Korgis resolves:

```text
registry key
   ↓
url
filename
backend
quantization
runtime params
   ↓
~/.local-llm/models/<filename>
```

If the key is missing, `local-llm download <key>` cannot work: there is no registry entry telling Korgis what artifact to fetch.

### 4.3 Verify a downloaded artifact

For benchmark evidence, hash the resolved local artifact:

```bash
uv run --frozen local-llm verify-artifact qwen3.5-4b-q4km
```

The command prints the computed SHA-256 and stores a local verification receipt. Compare the digest with the checksum published by the model source or with the checksum pinned by the benchmark/Korgis registry when one is available.

### 4.4 If Korgis does not have the model: option A — download it yourself

Download the exact GGUF from its authoritative source. For example:

```bash
mkdir -p ~/models/jev-bench

curl -L \
  "https://huggingface.co/<ORG>/<GGUF_REPO>/resolve/<REVISION>/<FILE>.gguf" \
  -o ~/models/jev-bench/<FILE>.gguf
```

Use an immutable revision/commit instead of `main` when reproducibility matters.

Check the local digest:

```bash
shasum -a 256 ~/models/jev-bench/<FILE>.gguf
```

Do not rename or substitute quantizations silently. Record the exact model, GGUF filename, quantization, source revision and SHA-256 used by the run.

### 4.5 One-off custom GGUF: bind the file directly with `--model-path`

For a quick single-model smoke test, Korgis can start a direct local GGUF even when the model is not in its registry:

```bash
cd ~/dev/korgis

uv run --frozen local-llm serve \
  --model my-local-model \
  --model-path "$HOME/models/jev-bench/my-model-Q4_K_M.gguf" \
  --backend llama_server \
  --ctx-size 8192 \
  --enable-admin-api \
  --no-download
```

Then verify:

```bash
curl http://127.0.0.1:1235/health
curl http://127.0.0.1:1235/v1/models
curl http://127.0.0.1:1235/v1/runtime/identity
```

This is useful for **one-off inference testing**.

It is **not the preferred setup for the multi-model benchmark**, because `compare-local` uses registry keys and Korgis' admin API to activate models sequentially.

### 4.6 Reusable custom GGUF: add it to the Korgis user registry

For benchmarking a model repeatedly, give it a stable Korgis key.

Korgis automatically merges:

```text
built-in registry
        ↓
optional external registries
        ↓
~/.local-llm/models.yaml
```

The user registry has the highest priority.

Create:

```text
~/.local-llm/models.yaml
```

with a local-path entry:

```yaml
models:
  my-model-4b-q4km:
    path: "/ABSOLUTE/PATH/my-model-4b-Q4_K_M.gguf"
    model_id: "org/model-4b"
    quantization: "Q4_K_M"
    backend: llama_server
    thinking_mode: none
    params:
      ctx_size: 8192
      startup_timeout: 300
      max_concurrent_requests: 1
      default_temperature: 0.0
      enable_thinking: false
      show_thinking: false
    tags: [local-benchmark, custom, 4b]
```

Now Korgis treats the manually downloaded file as a normal registered model:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm verify-artifact my-model-4b-q4km

uv run --frozen local-llm serve \
  --model my-model-4b-q4km \
  --enable-admin-api \
  --no-download
```

The benchmark can then use the same key:

```bash
cd ~/dev/experiments/experiments/jev-vs-llm

uv run jev-bench experiment routing \
  --provider korgis \
  --model my-model-4b-q4km
```

### 4.7 Alternative: teach Korgis how to download a custom model

Instead of downloading the GGUF manually, add `filename` + `url` to the user registry:

```yaml
models:
  my-model-4b-q4km:
    filename: "my-model-4b-Q4_K_M.gguf"
    url: "https://huggingface.co/<ORG>/<GGUF_REPO>/resolve/<REVISION>/my-model-4b-Q4_K_M.gguf"
    model_id: "org/model-4b"
    quantization: "Q4_K_M"
    sha256: "<EXPECTED_SHA256>"
    size_gb: 2.5
    backend: llama_server
    thinking_mode: none
    params:
      ctx_size: 8192
      startup_timeout: 300
      max_concurrent_requests: 1
      default_temperature: 0.0
      enable_thinking: false
      show_thinking: false
    tags: [local-benchmark, custom, 4b]
```

Then the normal Korgis workflow works:

```bash
uv run --frozen local-llm models
uv run --frozen local-llm download my-model-4b-q4km
uv run --frozen local-llm verify-artifact my-model-4b-q4km
```

The `sha256` field records the expected artifact identity. The current download command and artifact-verification command are separate operations, so run `verify-artifact` explicitly after downloading.

### 4.8 Experiment-specific registry instead of modifying your home directory

Korgis can also load one or more external YAML/JSON registry files through `LOCAL_LLM_REGISTRY_PATHS`.

Example:

```bash
export LOCAL_LLM_REGISTRY_PATHS="/absolute/path/benchmark-models.yaml"

uv run --frozen local-llm models
uv run --frozen local-llm download my-model-4b-q4km
uv run --frozen local-llm serve \
  --model my-model-4b-q4km \
  --enable-admin-api \
  --no-download
```

This is useful when the registry configuration belongs to an experiment and you do not want to modify `~/.local-llm/models.yaml`.

### 4.9 Start Korgis for the benchmark matrix

Once all desired model keys resolve correctly:

```bash
cd ~/dev/korgis

uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

The benchmark defaults to:

```text
http://127.0.0.1:1235/v1
```

In the benchmark shell:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export KORGIS_API_KEY="local"
```

Before running the benchmark:

```bash
curl http://127.0.0.1:1235/health
curl http://127.0.0.1:1235/v1/models
curl http://127.0.0.1:1235/v1/runtime/identity
```

For the default local matrix, Korgis activates one model at a time, runs its cases, returns to the anchor model and unloads temporary runtimes. This avoids keeping every GGUF resident simultaneously.

### 4.10 Which custom-model path should I use?

| Situation | Recommended path |
|---|---|
| Model already in Korgis registry | `local-llm download <key>` |
| Quick one-off GGUF smoke test | `serve --model-path ...` |
| Manually downloaded GGUF used repeatedly | add `path:` entry to user/external registry |
| Want Korgis to download a missing model | add `filename:` + `url:` entry |
| Multi-model `compare-local` | use stable registry keys for every model |

The benchmark should never depend on an unexplained local filename. Every local model used for comparative evidence should resolve through a documented Korgis registry key.

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

### Step 2 — run all four local models

This uses no Jev/OpenAI inference:

```bash
uv run jev-bench compare-local --profile budget
```

Default local matrix:

```text
Qwen3.5-4B Q4_K_M
MiniCPM3-4B Q4_K_M
Nemotron Nano 4B Q4_K_M
Qwen3.5-9B Q4_K_M
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
  --local-models qwen3.5-4b-q4km,minicpm3-4b-q4km,nemotron-nano-4b,qwen3.5-9b-q4km
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
- [x] MiniCPM3-4B Q4_K_M local baseline
- [x] Nemotron Nano 4B Q4_K_M local baseline
- [x] Qwen3.5-9B Q4_K_M local baseline
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

