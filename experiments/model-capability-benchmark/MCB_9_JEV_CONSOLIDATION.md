# MCB-9 — Jev consolidation on benchmark-core

Status: **IMPLEMENTED; CI validation pending**.

## Goal

Complete the migration without flattening Jev's bounded-decision semantics into the
generic capability benchmark.

The final dependency direction remains:

```text
Jev suite --------------------┐
                             v
                       benchmark-core
                             ^
model-capability-benchmark ---┘
```

The two experiment suites do not import one another.

## Shared implementation paths

MCB-9 consolidates the remaining infrastructure that was still duplicated.

### Public datasets

BANKING77 and CLINC150 now share benchmark-core primitives for:

- source/cache materialization;
- strict BANKING77 category/CSV parsing;
- CLINC split parsing and configured exclusion terms;
- DatasetSpec/YAML provenance.

Jev owns only its compatibility adapter from those rows to `BenchmarkCase`.

The historical Jev sampling algorithm is intentionally preserved because its case IDs and
ordered fixture selection are part of the regression baseline.

### Model/runtime registry

Jev now commits a portable typed `models.yaml` using the same benchmark-core
model/runtime/provider registry as the generic capability benchmark.

The repository no longer commits the old `benchmark-models.yaml` with absolute local
artifact paths.

Machine-local artifact resolution belongs to Korgis:

```text
Jev models.yaml
    model identity + runtime + quantization
              |
              v
runtime_model_id / Korgis key
              |
              v
Korgis built-in/user/external registry
              |
              v
local artifact path or download source
```

Use `LOCAL_LLM_REGISTRY_PATHS` when a model needs a machine-local external registry.

### Korgis lifecycle

The autonomous Jev local runner still owns optional Korgis **process lifecycle**, because
starting/stopping a developer checkout is intentionally not a generic benchmark-core
responsibility.

It no longer guesses personal paths. Korgis is resolved from:

- an already running endpoint; or
- `KORGIS_DIR`; or
- the repository sibling checkout.

`llama-server` is resolved from `LOCAL_LLM_SERVER_BIN` or `PATH`.

### Persistence, manifests, pricing and arm execution

These paths were already consolidated before MCB-9 and remain compatibility wrappers:

- CSV append -> `benchmark_core.persistence.append_csv_records`;
- environment manifest -> shared manifest writer;
- run identity -> shared run identity;
- pricing math/snapshot -> benchmark-core pricing;
- per-arm timing/failure boundary -> `BenchmarkArm / execute_arm`;
- summary primitives -> benchmark-core reporting.

The wrappers stay temporarily because the public Jev commands and row schema are stable
interfaces.

## Generic Jev task migration boundary

`JevDecisionTaskAdapter` now exposes Jev bounded decisions through the generic task
contract:

```text
BenchmarkCase
    |
    v
Sample
    |
    v
JevDecisionTaskAdapter.build_request
    |
    v
DecisionProviderInferenceAdapter
    |
    v
InferenceResult
    |
    v
JevDecisionTaskAdapter.evaluate
    |
    v
TaskResult
```

The task adapter does **not** move `QuestionSpec`, `choice`, `noul`, `score` or
workflow semantics into benchmark-core.

The legacy row runner and the generic task adapter call the same
`decision_correct(...)` implementation, preventing semantic drift.

## Intentionally Jev-specific components

The following remain in `jev_bench`:

- `QuestionSpec`;
- `DecisionProvider`;
- decision answer parsing;
- choice / noul / score semantics;
- deterministic expense/support workflow composition;
- monolithic workflow baselines;
- Jev-specific calibration interpretation;
- Jev HTML dashboard and its experiment-specific breakdowns/badges.

MCB-8 reporting is neutral and capability-oriented; replacing the richer Jev dashboard
would remove useful bounded-decision semantics rather than eliminate generic duplication.

## Compatibility guarantees

MCB-9 regression tests lock:

- existing smoke experiment row counts;
- request-level and question-level invalid semantics;
- append-only CSV behavior;
- legacy manifest shape;
- historical seeded BANKING77 fixture order and case IDs;
- BANKING77 / CLINC150 pinned revisions;
- generic Jev task output against legacy row semantics;
- portable model registry and absence of committed machine-specific paths.

## Migration guide

Existing Jev commands remain valid.

For local autonomous runs, the portable benchmark model catalog is now:

```text
experiments/jev-vs-llm/models.yaml
```

If the corresponding model key is not built into Korgis, configure an external Korgis
artifact registry:

```bash
export LOCAL_LLM_REGISTRY_PATHS="/path/to/local-korgis-models.yaml"
```

If the runner must launch Korgis itself:

```bash
export KORGIS_DIR="/path/to/korgis"
```

No migration requires copying local artifact paths into the experiments repository.

## Definition of Done

- [x] public dataset materialization/parsing has one shared core implementation path;
- [x] Jev public dataset revisions/URLs/filter terms are declarative;
- [x] Jev model/runtime/provider identity uses the shared typed registry;
- [x] committed machine-specific artifact paths are removed;
- [x] telemetry/manifests/persistence/pricing/arm primitives use benchmark-core;
- [x] a generic Jev task adapter exists;
- [x] legacy and generic Jev paths share bounded-decision correctness semantics;
- [x] Jev-specific evaluators/workflows/reporting remain isolated in Jev;
- [x] migration path for existing local commands is documented;
- [ ] focused MCB-9 CI passes;
- [ ] full Jev characterization/regression suite remains green;
- [ ] cumulative MCB/VLM/image-generation gates remain green.
