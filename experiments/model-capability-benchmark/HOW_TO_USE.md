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
nemotron-nano-4b
spark-x2.5-4b-q4km
ternary-bonsai2-27b-ptq1
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
