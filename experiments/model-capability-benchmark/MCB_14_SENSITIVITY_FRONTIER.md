# MCB-14 — Parameter Sensitivity & Local Pareto Frontier

## Goal

Extend Model Capability Benchmark from "which model performs best?" to two additional questions:

1. **How sensitive is one model to inference and runtime parameters?**
2. **Which model family / compression level sits on the best quality-resource frontier?**

The implementation reuses the existing task, dataset, evaluator, evidence, telemetry, projection and dashboard stack. It does not create a parallel benchmark harness.

## Experiment identity

A run now carries a configuration identity in addition to model, benchmark and execution identity:

~~~text
model
+ artifact / quantization
+ inference configuration
+ runtime configuration
+ benchmark
+ execution environment
~~~

The manifest persists a configuration object with configuration_id, experiment_kind, sweep_id, changed_dimension, is_baseline, inference and runtime fields.

Configuration IDs are deterministic hashes of the canonical inference/runtime config. They also participate in case identity through runner metadata so resume cannot silently reuse a case produced under another runtime configuration.

## Sensitivity sweeps

sweeps.yaml declares experiment matrices. Two strategies are supported.

### One-at-a-time

The default scientific mode changes one dimension around a fixed baseline.

~~~text
baseline
├── context 2K / 8K / 16K / 32K
├── max output 128 / 512 / 1024
├── temperature 0.2 / 0.7 / 1.0
└── top_p 0.8 / 0.9 / 1.0
~~~

This avoids a Cartesian explosion and makes each delta attributable to one parameter.

### Factorial

A focused factorial sweep is available after the one-at-a-time pass identifies an interesting region. It is intended for parameter interactions, not broad discovery.

## Inference vs runtime parameters

Inference parameters are request-scoped: temperature, max output tokens, top_p, top_k, min_p, repeat penalty, stop and seed.

Runtime parameters require the managed runtime to apply a deployment change: context size, KV limit, batch / micro-batch, threads, GPU layers, K/Q/V offload, flash attention, mmap, and thinking/runtime controls supported by Korgis.

MCB refuses a non-empty runtime override on a runtime that does not implement configuration. This is deliberate: a benchmark must not label a run "32K context" unless the serving runtime really applied it.

For Korgis, MCB sends the override through /api/v1/models/activate, then reads /health and validates the effective values before inference.

## Canonical CURRENT isolation

Sensitivity runs are stored as immutable normal runs, but they are **not eligible to replace canonical CURRENT benchmark results**.

The projector stores each run in run_configurations and the normal current-quality / current-performance views select only experiment_kind = standard.

This prevents, for example, a 32K context experiment from silently becoming the leaderboard result for that model.

## Sensitivity analytics

The cross-run sensitivity read model exposes for each configuration:

- capability primary quality metric;
- p50 / mean latency;
- output-token average;
- peak process RSS;
- quality delta vs baseline;
- latency % delta vs baseline;
- RSS % delta vs baseline.

Dashboard route: /sensitivity.

Filters: model × sweep × capability × parameter.

The UI shows the response curve and baseline-relative evidence table.

## Pareto Frontier

The frontier is computed from canonical standard CURRENT results, not from arbitrary sensitivity configurations.

Dashboard route: /frontier.

Selectable resource / complexity axis:

- total parameters;
- actual GGUF artifact size when observed;
- peak RSS;
- p50 latency.

Quality is maximized while the selected x-axis is minimized. A point is dominated when another measured point is at least as good on both dimensions and strictly better on one.

### Family scaling

Models are grouped by family and connected across parameter counts. This makes scaling curves such as 0.8B → 2B → 9B visible without collapsing them into a single ranking.

### Compression frontier

Variants with the same family + parameter count are grouped so quantizations can be compared on the same base model.

For managed local Korgis runs, MCB captures the actual model_path used by the runtime and records the on-disk artifact byte size when available. Static registry size remains a supported fallback.

## CLI

Inspect a sweep without inference:

~~~bash
uv run model-bench sweep \
  --model qwen3.5-9b-q4km \
  --sweep generation-sensitivity \
  --capabilities structured-output \
  --profile smoke \
  --run-group qwen9-sensitivity \
  --plan-only
~~~

Execute it:

~~~bash
uv run model-bench sweep \
  --model qwen3.5-9b-q4km \
  --sweep generation-sensitivity \
  --capabilities structured-output \
  --profile smoke \
  --run-group qwen9-sensitivity
~~~

Project all completed evidence:

~~~bash
uv run model-bench project --rebuild --export-dashboard
uv run model-bench dashboard-build
~~~

Then open /sensitivity or /frontier in the dashboard.

## Recommended experiment sequence

Do not start with a full factorial grid.

~~~text
1. canonical standard run
2. generation-sensitivity / smoke
3. inspect response curves
4. runtime-efficiency on promising dimensions
5. focused-interactions only around interesting knees
6. canonical core confirmation if a new deployment configuration is selected
~~~

This keeps the benchmark efficient while preserving enough evidence to distinguish quality gains from resource costs.

## Validation gates

MCB-14 CI covers sweep parsing/validation/deduplication, OVAT and factorial expansion, Korgis runtime override application, manifest configuration evidence, Pareto dominance/grouping, Python lint/compile/tests, React lint/build, and headless rendering of /frontier and /sensitivity.

Real Korgis validation remains an operational gate because CI does not have the local GGUF artifacts or Apple Silicon execution environment.
