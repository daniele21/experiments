# Model Capability Benchmark — How to Use

This is the recommended runbook for testing **one model at a time**.

The operational unit is:

~~~text
1 model × 1 capability × 1 profile = 1 immutable run
~~~

This is intentional: failures are easier to diagnose, and MCB can combine separate
completed runs later for cross-model comparison.

## 1. Current capability verticals

| Capability | Purpose | Core cases |
| --- | --- | ---: |
| structured-output | schema-constrained extraction | 60 |
| qa-abstention | grounded QA + abstention | 60 |
| mathematical-reasoning | final-answer reasoning | 40 |
| intent-classification | BANKING77 classification | 154 |
| oos-calibration | OOS detection + calibration | 154 |

Total core budget: **468 cases per model**.

As of suite v3, the `mathematical-reasoning` capability uses the new 72-case `math-reasoning-controlled-v3` dataset: **12 smoke, 40 core, 72 extended**. Core keeps the original 468-case total. Versions v1/v2 remain available in the dataset registry for historical runs. Do not interpret v2-v3 accuracy differences as model changes: run all compared models against the same v3 case set. Difficulty metadata is authored/provisional, not human-calibrated. To run the entire math v3 dataset, use `--profile extended --capabilities mathematical-reasoning`.

Recommended execution order:

~~~text
structured-output
→ qa-abstention
→ mathematical-reasoning
→ intent-classification
→ oos-calibration
~~~

The smaller controlled verticals come first so runtime/formatting problems are found
before the heavier classification runs.

## 2. The model-by-model workflow

For each model:

~~~text
preflight
→ plan
→ estimate
→ smoke each capability
→ core each capability
→ project
→ inspect dashboard
→ move to next model
~~~

Use **smoke** only to prove that a model/capability works.

Use **core** as the canonical result you want in the Results Explorer and in comparisons.

### Keep smoke out of canonical analytics

Store smoke runs under:

~~~text
results/scratch/
~~~

Store core runs under the default:

~~~text
results/runs/
~~~

The projector scans results/runs/ by default. This keeps diagnostic smoke evidence out
of CURRENT selection.

## 3. One-time MCB setup

From the repository root:

~~~bash
cd experiments/model-capability-benchmark
uv sync --extra dev

uv run model-bench models
uv run model-bench capabilities
uv run model-bench datasets
~~~

Current model keys:

~~~text
qwen3.5-2b-q4km
qwen3.8-27b-q40
nemotron-nano-4b
spark-x2.5-4b-q4km
ternary-bonsai2-27b-ptq1
lfm2.5-24b-a2b-ud-q3-k-xl
lfm2.5-24b-a2b-ud-q4-k-xl
limite-1b-violetto
gpt-5.6-luna
minicpm-v-4.6-1b
~~~

Install dashboard dependencies once:

~~~bash
cd dashboard
npm ci
cd ..
~~~

## 4. Local models through Korgis

Korgis must run externally with the admin API enabled.

From the Korgis checkout:

~~~bash
uv sync --frozen --extra dev

uv run --frozen local-llm models
uv run --frozen local-llm download qwen3.5-2b-q4km

uv run --frozen local-llm serve \
  --model qwen3.5-2b-q4km \
  --enable-admin-api \
  --no-download
~~~

Keep Korgis running.

In the MCB terminal:

~~~bash
export KORGIS_BASE_URL=http://127.0.0.1:1235/v1
export MCB_RESOURCE_TELEMETRY=1
export MCB_RESOURCE_SAMPLE_INTERVAL_MS=250
~~~

Check the runtime:

~~~bash
curl -fsS http://127.0.0.1:1235/health
curl -fsS http://127.0.0.1:1235/api/v1/resources
~~~

For Nemotron, download once:

~~~bash
uv run --frozen local-llm download nemotron-nano-4b
~~~

For Qwen3.8-27B Q4_0, Korgis first checks the LM Studio cache at
`~/.lmstudio/models/unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_0.gguf`.
The separate `MTP/mtp-Qwen3.8-27B-Q4_0.gguf` artifact is not the canonical
benchmark model and is intentionally not used by this baseline.

~~~bash
uv run --frozen local-llm models

uv run --frozen local-llm serve \
  --model qwen3.8-27b-q40 \
  --enable-admin-api \
  --no-download
~~~

The canonical Qwen3.8 baseline runs with thinking disabled and an 8192-token
runtime context, matching the controlled local-model policy. Treat MTP/speculative
decoding as a separate runtime-efficiency experiment so it does not change the
canonical capability lineage.

For Spark-X2.5-4B Q4_K_M, use llama.cpp build 10828 or newer. Korgis
enforces this model-specific runtime floor before loading the model, so an older
binary is rejected instead of producing misleading benchmark failures:

~~~bash
uv run --frozen local-llm download spark-x2.5-4b-q4km

uv run --frozen local-llm serve \
  --model spark-x2.5-4b-q4km \
  --enable-admin-api \
  --no-download
~~~

If Korgis reports that the discovered llama-server is older than build 10828,
update the normal llama.cpp installation or set `LOCAL_LLM_SERVER_BIN` to a
newer executable. Spark's native context is much larger than the benchmark
needs; the built-in Korgis benchmark profile intentionally uses 8192 tokens so
KV-cache overhead stays closer to the other local comparison models instead of
benchmarking an unnecessary long-context allocation.

Spark-X2.5 enables thinking in its upstream chat template by default. The Korgis
benchmark profile explicitly starts with thinking disabled, matching the
controlled local-model comparison policy. If a separate reasoning-on campaign is
run later, keep it as a distinct benchmark lineage rather than mixing it into the
default results.

For Ternary Bonsai 2 27B PTQ1_0, use the PrismML llama.cpp fork. Stock
llama.cpp does not support the PTQ1_0 ternary kernels. Korgis deliberately
requires a model-specific binary so other local models can keep using the normal
llama.cpp runtime:

~~~bash
export PRISM_LLAMA_SERVER_BIN="/absolute/path/to/prism-llama.cpp/build/bin/llama-server"

uv run --frozen local-llm download ternary-bonsai2-27b-ptq1

uv run --frozen local-llm serve \
  --model ternary-bonsai2-27b-ptq1 \
  --enable-admin-api \
  --no-download
~~~

Then, in the MCB terminal:

~~~bash
export KORGIS_BASE_URL=http://127.0.0.1:1235/v1
export MODEL=ternary-bonsai2-27b-ptq1

uv run model-bench validate-config --models "$MODEL"
uv run model-bench estimate \
  --models "$MODEL" \
  --profile core \
  --capabilities structured-output \
  --pilot-cases 3
~~~

Start with the normal smoke profile before changing generation settings. Bonsai 2
can spend a large part of a short output budget on reasoning; if the smoke run
returns empty answers, record that as evidence first rather than silently giving
this model a different benchmark configuration. Any later model-specific
reasoning/output override must create a distinct benchmark lineage.

MCB activates/releases the selected Korgis model. The Korgis server process remains
outside the benchmark. Korgis activation now returns a privacy-safe runtime identity;
MCB folds that fingerprint and backend build into the execution signature, so runs
made with different PrismML llama.cpp builds do not count as equivalent efficiency
experiments.

For fair local efficiency comparisons, keep the same Mac, Korgis version, MCB commit and
system conditions across models.

## 4b. Liquid Foundation Models (LFM2.5 24B A2B)

[LFM2.5-24B-A2B](https://huggingface.co/unsloth/LFM2.5-24B-A2B-GGUF) is an open-weight 24B Mixture-of-Experts model.

Both `UD-Q3_K_XL` (`lfm2.5-24b-a2b-ud-q3-k-xl`) and `UD-Q4_K_XL` (`lfm2.5-24b-a2b-ud-q4-k-xl`) quantizations are supported via Korgis (`llama_server` backend) resolving automatically from `~/.lmstudio/models/unsloth/LFM2.5-24B-A2B-GGUF/`:

~~~bash
# 1. In korgis terminal, start the server:
cd /Users/moltisantid/Personal/experiments/korgis
uv run local-llm serve --model lfm2.5-24b-a2b-ud-q4-k-xl --port 1235 --enable-admin-api
~~~

~~~bash
# 2. In model-capability-benchmark terminal:
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export MODEL="lfm2.5-24b-a2b-ud-q4-k-xl"

# Validate configuration
uv run model-bench validate-config --models "$MODEL"

# Plan benchmark across all capabilities
uv run model-bench plan --capabilities all --profile smoke

# Smoke test all capabilities (saved to scratch)
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile smoke \
  --run-group "lfm25-q4-smoke" \
  --output-dir results/scratch/lfm25-q4-smoke

# Canonical core benchmark across all capabilities
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile core \
  --run-group "lfm25-q4-core"

# Refresh analytics and dashboard
uv run model-bench project
uv run model-bench dashboard-data
uv run model-bench dashboard-build
~~~

## 4c. Liquid Foundation Models (LFM3 1.7B)

[LFM3-1.7B](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF) is Liquid AI's 1.7B model with native 256k context length.

`Q8_0` (`lfm3-1.7b-q8`) quantization is supported via Korgis (`llama_server` backend) resolving automatically from `~/.lmstudio/models/LiquidAI/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf`:

~~~bash
# 1. In korgis terminal, start the server:
cd /Users/moltisantid/Personal/experiments/korgis
uv run local-llm serve --model lfm3-1.7b-q8 --port 1235 --enable-admin-api
~~~

~~~bash
# 2. In model-capability-benchmark terminal:
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export MODEL="lfm3-1.7b-q8"

# Validate configuration
uv run model-bench validate-config --models "$MODEL"

# Plan benchmark across all capabilities
uv run model-bench plan --models "$MODEL" --capabilities all --profile smoke

# Smoke test all capabilities (saved to scratch)
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile smoke \
  --run-group "lfm3-q8-smoke" \
  --output-dir results/scratch/lfm3-q8-smoke

# Canonical core benchmark across all capabilities
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile core \
  --run-group "lfm3-q8-core"

# Refresh analytics and dashboard
uv run model-bench project
uv run model-bench dashboard-data
uv run model-bench dashboard-build
~~~

## 4d. Spark Models (Spark-X2.6 4B)

[Spark-X2.6-4B](https://huggingface.co/XHToken/Spark-X2.6-4B-GGUF) is an agentic, reasoning and coding model with a 1M token context window.

`Q4_K_M` (`spark-x2.6-4b-q4km`) is supported via Korgis (`llama_server` backend, requires modern `llama-server>=b11669`) resolving automatically from `~/.lmstudio/models/XHToken/Spark-X2.6-4B-GGUF/`:

~~~bash
# 1. In korgis terminal, start or activate the model:
cd /Users/moltisantid/Personal/experiments/korgis
uv run local-llm serve --model spark-x2.6-4b-q4km --port 1235 --enable-admin-api
~~~

~~~bash
# 2. In model-capability-benchmark terminal:
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export MODEL="spark-x2.6-4b-q4km"

# Validate configuration
uv run model-bench validate-config --models "$MODEL"

# Plan benchmark across all capabilities
uv run model-bench plan --models "$MODEL" --capabilities all --profile core

# Smoke test (saved to scratch)
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile smoke \
  --run-group "spark-x2.6-smoke" \
  --output-dir results/scratch/spark-x2.6-smoke

# Canonical core benchmark across all capabilities
uv run model-bench run \
  --models "$MODEL" \
  --capabilities all \
  --profile core \
  --run-group "spark-x2.6-core"

# Refresh analytics and dashboard
uv run model-bench project
uv run model-bench dashboard-data
uv run model-bench dashboard-build
~~~

## 5. API models

OpenAI:

~~~bash
export OPENAI_API_KEY="..."
~~~

MiniCPM / ModelBest:

~~~bash
export MINICPM_API_KEY="..."
# Optional:
# export MINICPM_BASE_URL=https://api.modelbest.cn/v1
~~~

TypeSafe Jev (System 1):

~~~bash
export TYPESAFE_API_KEY="..."
~~~

Decisio (Local GGUF via in-process Metal):

~~~bash
# Defaults to sibling checkout and ~/.lmstudio/models GGUFs
export DECISIO_ROOT="${HOME}/Personal/decisio"
export DECISIO_DEVICE="metal"
~~~

> [!NOTE]
> **Decision Models Scope**: Decision models like TypeSafe Jev (`jev-1.13.0`) and Decisio (`decisio-qwen3.5-2b-q4km`, `decisio-qwen3.5-4b-q4km`, `decisio-qwen3.5-9b-q4km`) evaluate discrete choice / bounded intent routing tasks. They are benchmarked **only** on classification capabilities (`intent-classification`, `oos-calibration`). Free-form generative capabilities (`qa-abstention`, `mathematical-reasoning`, `structured-output`) require autoregressive arbitrary text synthesis and are intentionally excluded.
>
> A dedicated launcher script is available:
> ~~~bash
> ./scripts/run_classification_benchmarks.sh
> ~~~

Secrets are read from the environment and are not persisted in benchmark manifests.


## 5b. Paradigma Limite 1B Violetto (Mathematical Reasoning)

[Paradigma Limite 1B - Violetto](https://huggingface.co/paradigma-inc/limite-1b-violetto) is a 1-billion parameter autoregressive language model specialized in competition-level mathematical reasoning.

It uses a canonical mathematical prompt (`"You are a helpful assistant. Please reason step by step, and put your final answer within \\boxed{}."`) and outputs step-by-step reasoning terminating in `\boxed{answer}`. MCB automatically:
1. Passes the raw math question without JSON schema pollution to preserve reasoning accuracy;
2. Extracts and normalizes the final `\boxed{answer}` into the structured capability evaluation field;
3. Supports the `--capabilities mathematics` alias for `mathematical-reasoning`;
4. Applies Paradigma's recommended sampling parameters (`temperature=0.6`, `top_p=0.95`) automatically when running default evaluations.

### Option A: In-Process Native Execution (Recommended on macOS / Local)

No external server or open port required. MCB runs inference directly in-process via PyTorch with Metal Performance Shaders (MPS) on Apple Silicon or CUDA on Linux:

~~~bash
export MODEL="limite-1b-violetto"
~~~

### Option B: vLLM serving (Remote or Linux GPU)

If serving via vLLM with the official Limite plugin:

~~~bash
VLLM_PLUGINS=limite uv run vllm serve paradigma-inc/limite-1b-violetto --port 8001
~~~

In your MCB terminal:

~~~bash
export VLLM_BASE_URL="http://127.0.0.1:8001/v1"
export MODEL="limite-1b-violetto-vllm"
~~~

### Option C: Local Korgis (Apple Silicon MLX & GGUF)

For native Apple Silicon Metal acceleration via Korgis using MLX:

~~~bash
# 1. Start Korgis with the MLX backend
cd /Users/moltisantid/Personal/experiments/korgis
uv run local-llm serve --model limite-1b-violetto-mlx --port 1235 --enable-admin-api

# 2. In model-capability-benchmark:
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export MODEL="limite-1b-violetto-mlx"
~~~

Or if running GGUF via a patched llama.cpp build with Limite architecture support:

~~~bash
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export MODEL="limite-1b-violetto-q80"  # Q8_0 GGUF (or limite-1b-violetto-q4km for Q4_K_M)
~~~

### Execute benchmark on mathematics

Validate preflight configuration:

~~~bash
uv run model-bench validate-config --models "$MODEL"
~~~

Inspect execution plan:

~~~bash
# Inspect plan for either version or both
uv run model-bench plan --capabilities math-v2,math-v3 --profile smoke
~~~

Run smoke test across both mathematics versions:

~~~bash
uv run model-bench run \
  --models "$MODEL" \
  --capabilities math-v2,math-v3 \
  --profile smoke \
  --run-group "limite-violetto-smoke-v2-v3"
~~~

Run full benchmark on Math v3 (72 cases):

~~~bash
uv run model-bench run \
  --models "$MODEL" \
  --capabilities math-v3 \
  --profile extended \
  --run-group "limite-violetto-v3-extended"
~~~

Run full benchmark on Math v2 (40 cases):

~~~bash
uv run model-bench run \
  --models "$MODEL" \
  --capabilities math-v2 \
  --profile core \
  --run-group "limite-violetto-v2-core"
~~~

Refresh DuckDB analytics and dashboard:

~~~bash
uv run model-bench project --rebuild --export-dashboard
~~~


## 6. Start one campaign

Choose a stable campaign name and one model:

~~~bash
export CAMPAIGN="2026-10-core-v1"
export MODEL="qwen3.5-2b-q4km"

git rev-parse HEAD
~~~

Keep the same MCB commit, profile, seed and benchmark configuration across models that
you intend to compare.

Preflight:

~~~bash
uv run model-bench validate-config --models "$MODEL"
~~~

Do not continue until this succeeds.

## 7. Plan without inference

~~~bash
uv run model-bench plan \
  --profile core \
  --capabilities all
~~~

This makes no provider/model calls.

## 8. Estimate before the full model

~~~bash
uv run model-bench estimate \
  --models "$MODEL" \
  --profile core \
  --capabilities all \
  --pilot-cases 5
~~~

Use this small pilot to catch runtime failures, unexpectedly slow local inference or API
cost surprises before running the 468-case model campaign.

## 9. Smoke a capability

Example:

~~~bash
export CAP="structured-output"
export RUN_ID="${CAMPAIGN}-${MODEL}-${CAP}-smoke"

uv run model-bench run \
  --run-group "${CAMPAIGN}-${MODEL}" \
  --run-id "$RUN_ID" \
  --output-dir "results/scratch/$RUN_ID" \
  --models "$MODEL" \
  --capabilities "$CAP" \
  --profile smoke
~~~

Inspect:

~~~bash
open "results/scratch/$RUN_ID/report.html"
~~~

Smoke passes when:

- model_failures == 0;
- failed_cases == 0, or every failure is understood;
- the primary metric exists;
- outputs look structurally correct;
- Korgis telemetry appears for local runs when resource observation is available.

Smoke is diagnostic, not the result to publish.

## 10. Run the canonical core vertical

Once smoke passes:

~~~bash
export RUN_ID="${CAMPAIGN}-${MODEL}-${CAP}-core"

uv run model-bench run \
  --run-group "${CAMPAIGN}-${MODEL}" \
  --run-id "$RUN_ID" \
  --models "$MODEL" \
  --capabilities "$CAP" \
  --profile core
~~~

The result is stored under:

~~~text
results/runs/<run-id>/
~~~

`run` shows live terminal progress by default: current model/capability and phase,
completed/failed/resumed cases, percentage, elapsed run time and ETA for the current
capability. Counts use the actual loaded samples. ETA appears after the first newly
executed case and uses observed case durations; resumed cases advance progress without
contributing to the timing estimate. Dataset loading, model preparation/release and report
rendering show their phase with elapsed time. ETA estimates case execution, not setup or
report rendering, and remains approximate when cases have different difficulty.

Progress refreshes every second in an interactive terminal, including during long provider
calls. Redirected stderr gets periodic plain-text updates (every 10 seconds plus lifecycle
boundaries). The final JSON stays on stdout. Use `--no-progress` to silence progress.

Inspect:

~~~bash
open "results/runs/$RUN_ID/report.html"
~~~

## 11. Resume or retry

Resume the same run by repeating the same command with the same run ID.

Retry only terminal failed cases:

~~~bash
uv run model-bench run \
  --run-group "${CAMPAIGN}-${MODEL}" \
  --run-id "$RUN_ID" \
  --models "$MODEL" \
  --capabilities "$CAP" \
  --profile core \
  --retry-failures
~~~

Do not reuse a run ID after changing model configuration, profile, capability, seed or
benchmark semantics. Start a new campaign/run instead.

## 12. Run all five core verticals for one model

### Consolidate runs by latest sample attempt

`model-bench consolidate` writes a new immutable run from existing evidence,
without inference. Repeat `--run-dir` for every base/recovery run to include:

```bash
uv run model-bench consolidate \
  --run-dir results/runs/base-run \
  --run-dir results/runs/recovery-run \
  --run-id model-consolidated-v1 \
  --run-group model-consolidated \
  --plan-only
```

Remove `--plan-only` to materialize the snapshot and report. The output must not
exist: use a new run ID for each new consolidation. Add all five base capability
runs to retain a complete model result, then include recovery runs as additional
sources. The source directory order does not affect selection.

The logical key includes model, capability, dataset revision/split, sample ID,
task version, prompt version and suite version. Selection uses the latest state
timestamp; ties use source run ID, attempt and case ID in that order. A newer
invalid result replaces an older valid result. Inference and evaluation are copied
from the same attempt. No latest incomplete/failed attempt without paired evidence
is silently dropped or replaced by an older success: consolidate rejects it and
requires recovery first. Profiles, seeds, artifacts and dataset/task definitions
must be compatible. Sources are checksumed before and after reading.

Each selected case retains its original run/case/attempt, generation settings,
timestamp and benchmark/runtime signatures. Aggregate metrics are recalculated on
the deduplicated cases; original runs are untouched. Mixed generation budgets are
explicit in the manifest and dashboard. Consolidated benchmark signatures are
separate from uniform-budget comparisons. Hardware/resource evidence is not
attributed to a single new execution of the consolidated cases.

```bash
uv run model-bench project --rebuild --export-dashboard
uv run model-bench dashboard-build
```

Dashboard exports default to `--result-view latest`: the newest completed
consolidated result replaces the base cells for that model/capability/profile;
other models keep their ordinary CURRENT cells. Recovery subsets alone never
replace complete results. Consolidated runs are labeled in the dashboard.
To inspect only ordinary uniform-configuration results instead:

```bash
uv run model-bench dashboard-data --result-view standard
uv run model-bench dashboard-build
```

The canonical SQL views `v_current_quality_results` and
`v_current_performance_results` remain restricted to standard runs. The dashboard's
latest selection is separately exposed as `v_latest_quality_results`.

### Recover only invalid or failed cases with a different output budget

Use `--rerun-errors-from` to select unsuccessful latest cases from a previous run.
This includes `completed` cases whose evaluation has `valid=false`, as well as
pipeline `failed` cases. Unlike `--retry-failures`, this creates a separate recovery
experiment and can change the token budget. A newer valid result for the same
model/capability/dataset/sample supersedes an earlier invalid result in the source
evidence. Repeat the source option to combine multiple run directories.

```bash
export BENCHMARK_TIMEOUT_SECONDS=180

uv run model-bench run \
  --models "$MODEL" \
  --capabilities structured-output \
  --profile core \
  --run-group "${CAMPAIGN}-recovery-4096" \
  --run-id "${CAMPAIGN}-${MODEL}-structured-output-recovery-4096" \
  --rerun-errors-from "results/runs/${CAMPAIGN}-${MODEL}-structured-output-core" \
  --max-output-tokens 4096 \
  --plan-only
```

Remove `--plan-only` to execute the selection. The preview does not contact a
provider or create output files. Keep the source profile and seed; requested samples
must still exist in the current dataset selection. Use a new run ID and output
directory. Recovery manifests record source run IDs, state checksums, selected
logical cases and the generation override; the original evidence is untouched.
Repeating the same recovery command resumes it. If selection or token override
changes, use another new run ID.

Recovery runs remain available in history but are excluded from canonical CURRENT
selection. Their scores measure recovery on an error-selected subset, not quality
on the complete benchmark. The existing `BENCHMARK_TIMEOUT_SECONDS` environment
variable controls provider request timeouts; more output tokens alone do not raise
the timeout. `--max-output-tokens` also works for ordinary full runs without editing
the shared suite configuration.

After you are comfortable running the first vertical manually:

~~~bash
CAPABILITIES=(
  structured-output
  qa-abstention
  mathematical-reasoning
  intent-classification
  oos-calibration
)

for CAP in "${CAPABILITIES[@]}"; do
  RUN_ID="${CAMPAIGN}-${MODEL}-${CAP}-core"

  uv run model-bench run \
    --run-group "${CAMPAIGN}-${MODEL}" \
    --run-id "$RUN_ID" \
    --models "$MODEL" \
    --capabilities "$CAP" \
    --profile core || break
done
~~~

The break is deliberate: if one vertical fails, inspect it before continuing the model
campaign.

## 13. Project after a completed core vertical

Incremental projection:

~~~bash
uv run model-bench project \
  --run-dir "results/runs/$RUN_ID" \
  --export-dashboard

uv run model-bench dashboard-build
open results/analytics/dashboard.html
~~~

You can therefore watch the Results Explorer grow while the campaign progresses.

For a clean rebuild from all immutable core evidence:

~~~bash
uv run model-bench project --rebuild --export-dashboard
uv run model-bench dashboard-build
~~~

## 14. Move to the next model

### One public JSON file for every dashboard view

Every dashboard export automatically replaces
`results/published/dashboard-data.json`. This is a single, versioned bundle with
`overview`, `capabilities`, `models` and `runs` maps: all routes, including frontier
and sensitivity (inside overview), can use the same snapshot. `generated_at_utc`
identifies when it was exported. The source is the selected analytics view, so
consolidated results and their mixed-budget labels are retained.

Both commands refresh the public bundle automatically:

```bash
uv run model-bench project --export-dashboard
uv run model-bench dashboard-data
```

The bundle is serialized completely and then atomically replaces the previous file.
Failed exports preserve the previous public file. Only files referenced by the
current export index are included; stale files are excluded. Known credential fields
and local filesystem paths are redacted, including serialized event metadata.
The original internal per-view exports remain available for local analysis.

Host this file at a stable URL, for example `/data/dashboard-data.json`. To make the
existing dashboard load all views dynamically, set this **before** its module script:

```html
<script>window.__MCB_DATA_URL__ = '/data/dashboard-data.json';</script>
```

The application fetches once on startup with `cache: 'no-store'`, validates the
bundle envelope and initializes every route from it. A load error is displayed
explicitly, without falling back to fixture data. Existing embedded/offline builds
continue to work when no URL is configured. An external page can also consume it:

```javascript
const response = await fetch('/data/dashboard-data.json', { cache: 'no-store' });
if (!response.ok) throw new Error(`Dashboard data: HTTP ${response.status}`);
const snapshot = await response.json();
const leaderboard = snapshot.overview.decision.model_summaries;
const capabilities = snapshot.capabilities;
const models = snapshot.models;
const runs = snapshot.runs;
```

Updating the local bundle does not upload it: the hosting/deployment pipeline must
sync `results/published/dashboard-data.json` to that URL. Serve JSON with compression
and, if hosted on a different origin, appropriate CORS headers. Reloading the page
loads the current snapshot; already-open pages do not poll automatically.

Example:

~~~bash
export MODEL="nemotron-nano-4b"
uv run model-bench validate-config --models "$MODEL"
~~~

Repeat the same sequence.

Then API:

~~~bash
export MODEL="gpt-5.6-luna"
uv run model-bench validate-config --models "$MODEL"
~~~

Do not delete previous runs. Separate model runs are intentionally combined later by the
projector.

## 15. What makes two results comparable?

### Quality

Quality comparison requires the same benchmark_signature.

Keep fixed during a comparison campaign:

- suite/task/evaluator versions;
- dataset revision and selection;
- profile;
- seed;
- generation configuration;
- MCB code revision.

The models can be executed in completely separate runs.

### Efficiency

Efficiency is stricter and requires compatible execution lineage.

The execution signature includes runtime/provider configuration plus privacy-safe hardware
identity:

- OS;
- machine architecture;
- CPU identity;
- total memory.

A run on an M3 Pro and one on an M4 Pro are therefore not treated as the same performance
experiment.

API and local efficiency are normally NON_COMPARABLE. API token pricing and local
CPU/RAM are different evidence domains.

## 16. What to inspect after each model

Quality:

- primary metric;
- family breakdown;
- invalid output rate;
- disagreements once another model exists.

Reliability:

- COMPLETED vs PARTIAL;
- failed cases;
- retries;
- typed provider/pipeline failures.

Local efficiency:

- latency;
- CPU average;
- RSS average/peak;
- telemetry sample count;
- telemetry errors;
- execution signature/hardware lineage.

Run and Model details now show the captured benchmark host CPU/chip, installed RAM,
architecture, OS and software versions. Compare shows each result's benchmark device
and links to its run evidence. These are captured run facts, not the machine currently
opening the dashboard; older runs without hardware evidence display unavailable values.

Korgis `/api/v1/resources` supplies runtime backend/scope, process CPU time and RSS,
host total/available RAM, and accelerator memory when supported. MCB samples it during
inference and persists `resource_samples.jsonl` and `resource_summary.jsonl`. Expand the
resource details for average/peak RSS, minimum available RAM, accelerator memory,
sampling interval, sample/error counts and measurement source. CPU percentages are
process CPU time divided by wall time (100% = one CPU core), and capability averages
are means of per-case measurements. RSS is process resident memory, not GPU memory.
Shared-server measurements may include other workloads. Loading and idle periods are
outside inference sampling.

The Korgis API currently does not provide a remote server's CPU/chip identity. The
benchmark host hardware is therefore labelled separately from runtime observations;
do not attribute the client machine's chip to a remote Korgis server. Thermal pressure
is available in the Korgis API but is not yet collected in MCB resource summaries.

Projecting existing runs backfills hardware from their captured manifests and Korgis
samples; no inference rerun is needed. Run `project --export-dashboard` followed by
`dashboard-build` to refresh the HTML.

Never interpret null telemetry as zero.

## 17. Compare two completed models

After two models have completed the same core capability:

~~~bash
uv run model-bench project --rebuild --export-dashboard
uv run model-bench dashboard-build
open results/analytics/dashboard.html
~~~

Use Compare to inspect quality delta, paired evidence, family differences and whether
efficiency is actually comparable.

## 18. Create LinkedIn-ready cards

Example:

~~~bash
uv run model-bench share create \
  --capability structured-output \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --title "Local vs API — Structured Output"
~~~

Then render the returned snapshot ID:

~~~bash
uv run model-bench share render \
  --snapshot <snapshot-id>
~~~

Outputs:

~~~text
results/shares/<snapshot-id>/
├── snapshot.json
├── card-01.png
├── card-02.png
├── card-03.png
├── card-04.png
├── card-05.png
└── carousel.pdf
~~~

The renderer reads only the immutable snapshot.

## 19. Recommended first real test

Start with one local model and the smallest high-signal vertical:

~~~bash
export CAMPAIGN="2026-10-first-real"
export MODEL="qwen3.5-2b-q4km"
export CAP="structured-output"

uv run model-bench validate-config --models "$MODEL"

uv run model-bench estimate \
  --models "$MODEL" \
  --profile core \
  --capabilities "$CAP" \
  --pilot-cases 5

RUN_ID="${CAMPAIGN}-${MODEL}-${CAP}-smoke"
uv run model-bench run \
  --run-group "${CAMPAIGN}-${MODEL}" \
  --run-id "$RUN_ID" \
  --output-dir "results/scratch/$RUN_ID" \
  --models "$MODEL" \
  --capabilities "$CAP" \
  --profile smoke

RUN_ID="${CAMPAIGN}-${MODEL}-${CAP}-core"
uv run model-bench run \
  --run-group "${CAMPAIGN}-${MODEL}" \
  --run-id "$RUN_ID" \
  --models "$MODEL" \
  --capabilities "$CAP" \
  --profile core

uv run model-bench project \
  --run-dir "results/runs/$RUN_ID" \
  --export-dashboard

uv run model-bench dashboard-build
open results/analytics/dashboard.html
~~~

If that works end to end, finish the other four verticals for Qwen before moving to
Nemotron and then API models.

## 20. Quality vs performance claims

The core campaign primarily answers:

> How capable is this model on this task vertical?

It also captures useful local latency/CPU/RAM evidence.

For stronger public claims about speed, thermals or resource efficiency, prefer a separate
small repeated-performance campaign on the same hardware:

~~~text
same model
same capability
same cases/config
same hardware
3 repeated runs
~~~

That reduces performance noise without inflating the quality benchmark to thousands of
redundant examples.

## 21. Parameter sensitivity experiments

Sensitivity is a separate experiment lineage from the canonical CORE result. Start by
inspecting the generated matrix without invoking the model:

~~~bash
export MODEL="qwen3.5-9b-q4km"

uv run model-bench sweep \
  --model "$MODEL" \
  --sweep generation-sensitivity \
  --capabilities structured-output \
  --profile smoke \
  --run-group "${CAMPAIGN}-${MODEL}-sensitivity" \
  --plan-only
~~~

The default generation-sensitivity sweep uses one-at-a-time variation around a fixed
baseline for context size, max output tokens, temperature and top_p. This keeps the
experiment small enough to run locally and makes each delta interpretable.

Execute the sweep after reviewing the plan:

~~~bash
uv run model-bench sweep \
  --model "$MODEL" \
  --sweep generation-sensitivity \
  --capabilities structured-output \
  --profile smoke \
  --run-group "${CAMPAIGN}-${MODEL}-sensitivity"
~~~

For runtime-focused work use runtime-efficiency. Use focused-interactions only after the
one-at-a-time experiment has identified an interesting region.

Runtime dimensions such as ctx_size are applied through Korgis model activation and then
verified against /health. MCB rejects runtime overrides on runtimes that cannot apply them.

Sensitivity runs live under results/runs like all immutable evidence, but the projector
marks them experiment_kind=sensitivity and excludes them from the canonical CURRENT
leaderboard.

Refresh analytics after the sweep:

~~~bash
uv run model-bench project --rebuild --export-dashboard
uv run model-bench dashboard-build
~~~

Open the dashboard and use /sensitivity to choose model, sweep, capability and parameter.
The evidence table reports quality, p50 latency and peak RSS plus deltas versus the sweep
baseline.

## 22. Family and compression Pareto Frontier

The /frontier route is built from canonical standard CURRENT results. It does not mix
arbitrary sensitivity points into the model leaderboard.

Use the X-axis selector to compare quality against:

- parameter count, for family scaling;
- measured GGUF artifact size, for compression;
- peak RSS, for deployment memory;
- p50 latency, for responsiveness.

Use "Model family scaling" to connect variants across parameter counts. Use "Compression
variants" to connect quantizations of the same family and base parameter count.

For local Korgis runs, MCB records the actual loaded artifact size when model_path is
available, so Q4/Q8/PTQ comparisons can use the bytes of the artifact that really ran.

A faded point is dominated for the selected axis; a solid point is Pareto-efficient.
Keep hardware and benchmark lineage fixed before turning a Pareto observation into a
performance claim.

## 23. Troubleshooting

Korgis preflight fails:

~~~bash
echo "$KORGIS_BASE_URL"
curl -fsS http://127.0.0.1:1235/health
~~~

Korgis must be started with --enable-admin-api.

Telemetry missing:

~~~bash
curl -fsS http://127.0.0.1:1235/api/v1/resources
echo "$MCB_RESOURCE_TELEMETRY"
~~~

The resources response should contain observation. Unset or 1 enables telemetry; off,
false, no or 0 disables it.

API preflight fails: verify the matching OPENAI_API_KEY or MINICPM_API_KEY in the current
shell.

PARTIAL run: inspect events.jsonl and report.html, fix the root cause, then rerun the same
run ID with --retry-failures.

## 24. Operational rule

~~~text
SMOKE   = can this model/task run correctly?
CORE    = what result do I trust and compare?
PROJECT = make immutable evidence queryable
SHARE   = freeze one result story for publication
~~~

This keeps model-by-model testing efficient, debuggable and publishable.
