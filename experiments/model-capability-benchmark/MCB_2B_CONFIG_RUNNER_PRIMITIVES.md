# MCB-2B — Config and Runner Primitives

Status: **COMPLETE** — frozen/config-runner gate green (22/22 focused tests) and full Jev characterization suite green (51/51).

MCB-2B continues the shared-core extraction after MCB-2A, focusing on medium-coupling
utilities that are already duplicated across the local Korgis and CLM matrix runners.

## Extracted components

### Shared YAML config loading

New package:

- `benchmark_core.config`.

It provides:

- safe YAML mapping loading;
- named mapping-section loading;
- CSV selection parsing;
- stable deduplication preserving input order;
- explicit `ConfigError` failures.

`scripts/run_local_matrix.py` keeps its existing `load_config` and
`load_registry_models` functions as compatibility wrappers, but their implementation now
lives in benchmark-core.

This is infrastructure extraction only. The schema of `benchmark-models.yaml` remains
Jev/Korgis-specific until MCB-3.

### Generic matrix-arm boundary

New package:

- `benchmark_core.runner`.

`BenchmarkArm` identifies one `model × task` execution.

`execute_arm` owns:

- elapsed-time measurement;
- success/error normalization;
- exception type/message capture.

It deliberately does **not** own:

- provider construction;
- runtime lifecycle;
- task dispatch;
- persistence policy;
- retries;
- model activation.

Those responsibilities remain with the suite/runtime layer until the later registry and
unified-runner workstreams.

Both the local Korgis orchestrator and the CLM matrix runner now use this same execution
boundary.

### Shared lightweight summary

New package:

- `benchmark_core.reporting`.

`summarize_records` computes the current matrix-run summary fields from generic mappings:

- total cases;
- valid cases;
- correct cases;
- accuracy percentage;
- average latency.

The shared implementation has no pandas dependency. Jev adapters convert DataFrames to
records at their boundary.

## Preserved semantics

MCB-2B intentionally preserves:

- local/CLM CLI flags;
- local/CLM model ordering;
- CLM `all` experiment behavior;
- public-vs-smoke experiment restrictions;
- per-arm persistence;
- per-arm failure isolation;
- current summary field names;
- current report and manifest generation.

Lifecycle remains runtime-specific:

```text
Korgis: activate → run arms → unload
CLM: preflight endpoint → run arms
```

The shared runner primitive sits inside those flows instead of replacing them.

## Dependency change

benchmark-core now depends on `PyYAML` because YAML configuration is a first-class shared
input format for the benchmark platform.

The Jev lockfile already contained PyYAML and is updated so the local benchmark-core
package declares the dependency correctly under frozen installs.

## Deferred to later workstreams

MCB-2B does not yet create the unified model/runtime registry. In particular it does not
solve the machine-specific paths currently present in `benchmark-models.yaml`; that
belongs to MCB-3 where model metadata and runtime configuration are separated.

It also does not replace the Jev task `if/elif` dispatch; that belongs to MCB-4.

## Definition of Done

- [x] YAML loading is shared;
- [x] CSV selection parsing is shared;
- [x] model×task arm identity is generic;
- [x] per-arm timing/error capture is shared;
- [x] local and CLM matrix runners use the shared arm boundary;
- [x] local and CLM summaries share one record-level implementation;
- [x] benchmark-core remains independent from Jev;
- [x] frozen dependency sync passes;
- [x] focused MCB-2B tests pass (22/22);
- [x] MCB-1 core-contract gate remains green;
- [x] full Jev characterization suite remains green (51/51).
