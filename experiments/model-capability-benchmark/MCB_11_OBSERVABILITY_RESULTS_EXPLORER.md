# MCB-11 — Benchmark Observability, Results Explorer & Shareable Insights

Status: **IN PROGRESS — FOUNDATION VERTICAL SLICE IMPLEMENTED**

Depends on: **MCB-10 — Vertical Benchmark Hardening & Efficiency**

Implemented in the first vertical slice:

- typed lifecycle event envelope with raw/evaluation evidence references;
- deterministic model / benchmark / execution signatures;
- benchmark identity excludes presentation-only practical-delta thresholds;
- one immutable folder per generated run ID by default;
- CURRENT/HISTORICAL/PARTIAL canonical selection;
- expected-cell validation so incomplete runs cannot become CURRENT;
- rebuildable DuckDB projector with MCB-10 fallback signatures;
- typed overview/capability dashboard export;
- backend-derived family breakdown, disagreements and paired statistics;
- React/Vite routes for Overview, Structured Output, Disagreements and Share preview;
- single-file dashboard data injection;
- immutable `share create` snapshot contract;
- fixture, projection and integration tests authored.

Still pending in later slices:

- Model profile/history;
- full Run explorer/timeline UI;
- Compare UI;
- resource telemetry;
- STALE/NON_COMPARABLE presentation across all screens;
- PNG/PDF headless share renderer and visual regression;
- expansion from structured-output to all five capabilities;
- local Python/frontend gate execution and visual validation.

## 1. Objective

Turn the Model Capability Benchmark from a per-run HTML report into a durable benchmark observability and analysis product.

The system must support four distinct needs without coupling them together:

1. preserve complete, reproducible benchmark evidence;
2. rebuild cross-run analytics deterministically from that evidence;
3. make benchmark results understandable through progressive disclosure;
4. freeze selected benchmark findings into immutable, shareable artifacts suitable for LinkedIn.

The central design rule is:

```text
immutable benchmark evidence
          ↓
deterministic projector
          ↓
analytics read model
          ↓
typed UI payloads
     ┌────┴────┐
     ↓         ↓
results UI   share renderer
```

The UI must never become the source of truth.

There is still no mandatory overall model score.

---

## 2. Product questions the UI must answer

### Result questions

- Which model is sufficient or best for a specific capability?
- Where are two models practically equivalent?
- Where does one model clearly outperform another?
- Which case families explain the gap?
- Is the result based on the same exact cases?
- What are latency, token and cost trade-offs?
- Has the result improved or regressed over time?

### Operational questions

- Is a run currently complete, partial, failed or stale?
- Where did a failure happen: runtime, request, provider, evaluation or projection?
- Which exact attempt produced the result?
- What was the effective benchmark/model/runtime configuration?
- Can the derived analytics be rebuilt from raw evidence?

### Sharing questions

- Can one finding be frozen independently from future dashboard updates?
- Can a LinkedIn graphic show methodology and provenance without becoming visually noisy?
- Can a reader trace a public card back to the exact benchmark configuration?

---

## 3. Non-goals

MCB-11 does not:

- replace raw JSONL evidence with a database;
- delete historical runs;
- select a global "best model";
- hide provider/runtime failures as wrong answers;
- query live provider APIs while rendering historical results;
- make the browser responsible for reconstructing benchmark science;
- silently compare incompatible benchmark revisions;
- treat local provider fee = 0 as total local cost = 0.

---

# 4. Target architecture

```text
model-bench run
    │
    ├── run_manifest.json
    ├── environment.json
    ├── state.jsonl
    ├── events.jsonl
    ├── raw.jsonl
    ├── evaluation.jsonl
    ├── aggregates.jsonl
    └── report_index.jsonl
             │
             ▼
      MCB projector
             │
      ┌──────┴────────┐
      ▼               ▼
 benchmark.duckdb   projection manifests
      │
      ├── canonical latest views
      ├── comparable result views
      ├── trends
      ├── disagreement indexes
      ├── case-family breakdowns
      └── run health
             │
             ▼
       dashboard export
             │
             ▼
   dashboard/data/*.json
             │
             ▼
 React/Vite static dashboard
             │
      ┌──────┴───────┐
      ▼              ▼
 interactive UI   share snapshot
                       │
                       ▼
                 fixed-size renderer
                       │
                 PNG / PDF carousel
```

## Source of truth

The source of truth remains the immutable run evidence and manifests.

DuckDB and dashboard JSON are disposable projections:

```text
delete benchmark.duckdb
        ↓
model-bench project --rebuild
        ↓
same analytics reconstructed
```

---

# 5. Storage layout

Target layout:

```text
experiments/model-capability-benchmark/
├── results/
│   ├── runs/
│   │   └── <run-id>/
│   │       ├── run_manifest.json
│   │       ├── environment.json
│   │       ├── state.jsonl
│   │       ├── events.jsonl
│   │       ├── raw.jsonl
│   │       ├── evaluation.jsonl
│   │       ├── aggregates.jsonl
│   │       ├── report_index.jsonl
│   │       ├── report.json
│   │       └── report.html
│   │
│   ├── analytics/
│   │   ├── benchmark.duckdb
│   │   ├── projection_manifest.json
│   │   └── dashboard/
│   │       ├── index.json
│   │       ├── overview.json
│   │       ├── capabilities/
│   │       ├── models/
│   │       ├── runs/
│   │       └── comparisons/
│   │
│   └── shares/
│       └── <snapshot-id>/
│           ├── snapshot.json
│           ├── card-01.png
│           ├── card-02.png
│           ├── ...
│           └── carousel.pdf
│
└── dashboard/
    ├── package.json
    ├── src/
    └── ...
```

Generated analytics, images and database artifacts should remain ignored unless an explicit golden fixture is required.

---

# 6. MCB-11A — Typed observability envelope

## Goal

Make lifecycle logs structured enough to be consumed mechanically without duplicating raw benchmark payloads.

## Event envelope

Every lifecycle event should expose a common envelope:

```python
BenchmarkEvent(
    schema_version: str,
    event_id: str,
    event_type: str,
    timestamp_utc: str,

    run_id: str,
    run_group: str,

    model_key: str | None,
    model_signature: str | None,

    capability_id: str | None,
    dataset_id: str | None,
    sample_id: str | None,
    case_id: str | None,
    attempt: int | None,

    benchmark_signature: str | None,
    execution_signature: str | None,

    status: str | None,
    duration_ms: float | None,

    payload_ref: EvidenceRef | None,
    metadata: Mapping[str, Any],
)
```

## Event taxonomy

Run:

```text
run.started
run.completed
run.failed
run.interrupted
```

Runtime/model lifecycle:

```text
model.prepare.started
model.prepare.completed
model.prepare.failed
model.release.started
model.release.completed
model.release.failed
```

Capability:

```text
capability.started
capability.completed
capability.aggregated
capability.failed
```

Case:

```text
case.started
request.built
request.failed
inference.started
inference.completed
inference.failed
evaluation.started
evaluation.completed
evaluation.failed
case.completed
case.failed
```

Projection:

```text
projection.started
projection.completed
projection.failed
share.created
share.rendered
```

## Payload policy

Events must contain summary metadata, never duplicate large raw payloads.

For example:

```text
inference.completed
  duration_ms: 1842
  valid: true
  input_tokens: 321
  output_tokens: 48
  estimated_cost_usd: 0.00012
  payload_ref:
    file: raw.jsonl
    case_id: ...
    attempt: 1
```

The raw model output remains in raw evidence.

## Backward compatibility

- existing `EvidenceStore.record_event()` remains temporarily supported;
- projector supports current MCB-10 events and new typed events;
- new runner code writes typed events;
- old runs remain projectable with reduced timeline detail.

## Definition of Done

- event schema is versioned;
- every event has deterministic run/case linkage when applicable;
- raw output is referenced, not copied;
- old MCB-10 run folders remain readable;
- fake-run tests cover happy path and failures.

---

# 7. MCB-11B — Model, benchmark and execution signatures

## Goal

Define comparability explicitly.

"Latest" must mean latest comparable completed evidence, not newest file timestamp.

## 7.1 Model signature

Represents the evaluated model identity.

Inputs:

```text
model_key
canonical model_id
model revision when known
runtime_model_id/effective_model_id
artifact format
quantization
relevant inference-affecting model metadata
```

Provider identity is retained separately. Provider/runtime compatibility changes that alter observable generation semantics must be represented either in the model signature or benchmark execution contract.

Example:

```text
sha256:model:...
```

Q4_K_M and Q8 variants must never collapse into one model signature.

## 7.2 Benchmark signature

Represents "what exactly was measured".

Inputs:

```text
suite_id + suite_version
capability_id
task_id + task_version
prompt_id + prompt_version
evaluator_version

dataset IDs + revisions + splits
selection fingerprint(s)
profile/tier
generation parameters
seed
comparison metric
serving-mode semantics when quality-affecting
```

If any of these changes, the result becomes a different benchmark signature.

## 7.3 Execution signature

Represents the environment required for performance comparability.

Inputs where available:

```text
runtime key/type/version
backend
hardware identity
CPU/GPU/accelerator
RAM/VRAM class
OS
threading/concurrency
context/runtime parameters
Korgis/runtime configuration
```

Quality comparisons can use model + benchmark signatures.

Performance comparisons require:

```text
model_signature
+
benchmark_signature
+
execution_signature
```

## 7.4 Signature versioning

Never silently change hash input semantics.

Use:

```text
signature_schema_version = "1"
```

If signature inputs change materially, bump the signature schema.

## Definition of Done

- canonical serializer is deterministic;
- signatures are persisted in run/case metadata;
- golden tests freeze known signatures;
- different quantization yields different model signature;
- different evaluator/dataset selection yields different benchmark signature;
- hardware/runtime change yields different execution signature.

---

# 8. MCB-11C — Run lifecycle and canonical result policy

## Goal

Create a deterministic rule for the result shown by default.

## Run status

Derived run status:

```text
RUNNING
COMPLETED
PARTIAL
FAILED
INTERRUPTED
INVALID
```

A completed quality result requires:

- run reached terminal completion;
- all expected capability/model cells are terminal;
- aggregate evidence is internally consistent;
- manifest is readable;
- projection validation passes.

Partial runs remain visible in the Runs section but cannot replace the canonical result.

## Canonical latest quality result

Grouping key:

```text
model_signature
+
benchmark_signature
```

Selection:

```text
only valid completed results
ORDER BY completed_at_utc DESC, run_id DESC
LIMIT 1
```

## Canonical latest performance result

Grouping key:

```text
model_signature
+
benchmark_signature
+
execution_signature
```

Selection uses the same terminal/valid rule.

## Result presentation state

Every projected result receives:

```text
CURRENT
HISTORICAL
STALE
NON_COMPARABLE
PARTIAL
```

Definitions:

- CURRENT: latest valid result for its exact comparable signature;
- HISTORICAL: older result with same comparable signature;
- STALE: valid result for an older benchmark/model signature when a newer revision exists;
- NON_COMPARABLE: visible result that cannot enter the selected comparison;
- PARTIAL: non-terminal/incomplete execution.

## Why not overwrite history

A failed Oct 5 rerun must not hide a valid Oct 3 result.

A changed evaluator must not replace an older result in the same trend line.

The UI may default to CURRENT but must retain historical navigation.

## Definition of Done

- canonical latest selection is deterministic;
- incomplete run never replaces completed result;
- changed benchmark signature starts a separate comparison lineage;
- quality and performance latest policies are distinct;
- tests cover ties, retries, partial runs and stale revisions.

---

# 9. MCB-11D — DuckDB analytics projector

## Goal

Create a rebuildable analytical read model optimized for cross-run queries.

## Dependency

Add DuckDB to the Python experiment dependencies.

No DuckDB requirement is introduced into `benchmark-core` unless later proven generic.

## Projector commands

```bash
uv run model-bench project

uv run model-bench project --rebuild

uv run model-bench project   --run-dir results/runs/<run-id>
```

Default behavior:

- discover new/changed completed run folders;
- verify artifact checksums/metadata;
- upsert by immutable run/case identities;
- update derived views transactionally;
- write projection manifest.

## Core tables

### runs

```text
run_id PK
run_group
suite_id
suite_version
profile
seed
started_at_utc
completed_at_utc
status
git_commit
manifest_checksum
pricing_as_of
projection_status
```

### models

```text
run_id
model_key
model_id
effective_model_id
model_signature
runtime_key
provider_key
deployment
quantization
artifact_format
```

### benchmark_cells

One model × capability × benchmark signature per run.

```text
run_id
model_signature
benchmark_signature
execution_signature
capability_id
task_id
dataset_ids
profile
sample_count
failure_count
status
```

### cases

```text
run_id
case_id
attempt
model_signature
benchmark_signature
execution_signature
capability_id
dataset_id
sample_id
family
difficulty
challenge_type
inference_valid
evaluation_valid
latency_ms
input_tokens
cached_input_tokens
output_tokens
estimated_cost_usd
error_kind
```

Large raw output should remain referenced through evidence location rather than copied blindly into analytical columns.

### case_metrics

```text
run_id
case_id
attempt
metric
value
primary
```

### aggregates

```text
run_id
model_signature
benchmark_signature
capability_id
metric
value
sample_count
failure_count
primary
```

### comparisons

Materialized/rebuildable paired comparison result:

```text
benchmark_signature
model_a_signature
model_b_signature
capability_id
metric
paired_count
delta_b_minus_a
ci95_low
ci95_high
both_correct
a_only_correct
b_only_correct
both_wrong
mcnemar_exact_p
practical_delta
exceeds_practical_delta
```

### events

Typed event envelope optimized for run timeline.

### resource_samples

Reserved for local performance telemetry:

```text
run_id
model_signature
timestamp_utc
cpu_percent
rss_bytes
system_ram_bytes
gpu_memory_bytes
tokens_per_second
source
```

Fields remain nullable when a runtime cannot supply them.

### share_snapshots

Metadata/index only; immutable snapshot payload also lives on disk.

## Derived views

Minimum SQL views:

```text
v_current_quality_results
v_current_performance_results
v_run_health
v_model_capability_matrix
v_capability_breakdown_family
v_capability_breakdown_difficulty
v_pairwise_current
v_disagreements
v_model_history
v_benchmark_lineages
```

## Projection invariants

- projector is idempotent;
- source artifact never mutated;
- same source -> same analytical values;
- projection failure does not invalidate source run;
- projection manifest records schema version and source checksums.

## Definition of Done

- DB rebuild works from empty state;
- incremental projection matches rebuild output;
- duplicate projection does not duplicate rows;
- corrupted/incomplete run is quarantined from CURRENT views;
- SQL contract tests freeze key latest/comparability behavior.

---

# 10. MCB-11E — Dashboard export contract

## Goal

Keep frontend simple and static while analytics stay powerful.

Do not run DuckDB/WASM in the browser in v1.

Python exports typed UI payloads:

```bash
uv run model-bench dashboard-data
```

or as part of:

```bash
uv run model-bench project --export-dashboard
```

## Payload split

Avoid one enormous `benchmark_data.json`.

Suggested files:

```text
dashboard/index.json
dashboard/overview.json
dashboard/capabilities/<capability-id>.json
dashboard/models/<model-signature>.json
dashboard/runs/<run-id>.json
dashboard/comparisons/<comparison-id>.json
```

`index.json` contains lightweight navigation metadata only.

## Payload rules

- payloads contain already-derived analytical facts;
- frontend does not recompute benchmark statistics;
- every displayed metric includes lineage/provenance IDs;
- unknown values remain null;
- display labels are separate from identity keys.

## Definition of Done

- dashboard can be built without provider credentials;
- dashboard payload generation is deterministic;
- data contract has TypeScript types and Python contract tests;
- large raw evidence is loaded only for case drill-down.

---

# 11. MCB-11F — Dashboard foundation and routing

## Goal

Create a dedicated MCB dashboard while reusing proven repository frontend patterns.

## Stack

Reuse the Jev dashboard baseline:

- React 19;
- TypeScript;
- Vite;
- Lucide icons;
- single-file/static build pattern where useful.

Do not copy Jev-specific leaderboard/verdict policy.

Potential low-level reusable primitives may be extracted later only if duplication becomes material.

## Routing

Use real URL routes, not a single hash-tab state:

```text
/                         -> redirect /overview
/overview
/capabilities/:capabilityId
/capabilities/:capabilityId/disagreements
/models/:modelSignature
/runs
/runs/:runId
/compare
/share
/share/:snapshotId
```

Selected filters should be reflected in query parameters where useful:

```text
?profile=core
&models=qwen...,gpt...
&dataset=...
&state=current
```

This makes views deep-linkable and shareable.

## Global navigation

Sidebar:

```text
Overview
Models
Capabilities
Runs
Compare
Share

Settings
Docs
```

## Global filters

At minimum:

- benchmark lineage/profile;
- model set;
- dataset where applicable;
- result state: Current / History;
- quality vs performance context where needed.

## Visual principles

- neutral comparison, no celebratory "winner";
- primary quality metric emphasized;
- uncertainty and paired n visible near deltas;
- metadata progressively disclosed;
- failures never hidden inside quality;
- dark/light compatible;
- responsive desktop-first;
- LinkedIn export is a separate controlled layout, not a screenshot of arbitrary dashboard state.

---

# 12. MCB-11G — Overview dashboard

## Goal

Answer "which model is suitable for which workload?" in less than 10 seconds.

## Header

Show:

```text
suite/version
profile
cases per model
benchmark commit
latest projection time
comparability status
```

## Primary capability matrix

Rows:

```text
Intent classification
OOS / calibration
Structured output
QA / abstention
Mathematical reasoning
```

Columns are selected models.

Cell:

```text
primary quality value
sample count
failure count
optional paired delta indicator
```

Do not combine rows into an overall score.

## Cell status

Use explicit semantic states:

```text
comparable
practically equivalent
meaningful delta
insufficient paired evidence
non-comparable
stale
```

Avoid relying on color alone.

## Secondary summary

For selected models:

- latency p50/p95;
- total known API cost;
- local/API badge;
- peak resource metrics when known;
- invalid/failure rate.

## Interactions

Click a capability -> capability detail.

Click model -> model profile.

Click status/failure -> filtered run/case view.

---

# 13. MCB-11H — Capability detail

## Goal

Explain not only the quality difference but its cause.

## Hero comparison

For selected model pair:

```text
Model A primary score
Model B primary score
delta B-A
95% paired CI
paired n
practical delta
McNemar p
```

## Breakdown tabs

```text
Overview
By family
By difficulty
Disagreements
Examples
Analysis
```

## Family/difficulty table

Each row:

```text
dimension value
A score / n
B score / n
delta
failure count
```

## Statistical labeling

Examples:

- `+1.2 pp · below practical threshold`;
- `+9.1 pp · CI excludes 0`;
- `insufficient paired evidence`.

Do not render a binary "winner" badge from p-value alone.

## Definition of Done

- vertical breakdown works for controlled dataset metadata;
- public datasets without family metadata degrade gracefully;
- paired metrics are loaded from projector output, not recomputed in React.

---

# 14. MCB-11I — Disagreement & case explorer

## Goal

Make failure analysis a first-class workflow.

## Filters

```text
All
A only correct
B only correct
Both wrong
Models disagree
Provider/evaluator failures

Family
Difficulty
Challenge type
Dataset
```

## Case list

Each item shows:

```text
sample id
family
difficulty
short input preview
outcome badge for each selected model
```

## Case detail

Three-column structure where space permits:

```text
Input / expected
Model A
Model B
```

Per model:

- normalized output;
- correctness;
- per-case metrics;
- latency/tokens/cost;
- inference/evaluation validity;
- expandable raw output;
- attempt number;
- evidence reference.

Raw evidence is opt-in progressive disclosure.

## Safety against misleading comparisons

Only classify a case as "A only correct/B only correct/both wrong" when both model evaluations are valid and paired on the same benchmark/sample identity.

Pipeline failures get a separate state.

---

# 15. MCB-11J — Model profile and history

## Goal

Show the current capability profile of one exact model signature and how it evolves.

## Current profile

```text
model identity
revision
quantization
runtime/provider
deployment
current benchmark lineage
```

Capability list:

```text
capability
primary metric
n
status
last completed
```

## Efficiency panel

When available:

- latency p50/p95;
- throughput/tokens/s;
- model startup time;
- known API cost;
- peak RSS/system RAM;
- GPU/accelerator memory;
- execution signature/hardware.

## History

History must never mix different benchmark signatures into a continuous line.

UI behavior:

- default: same benchmark signature only;
- optional: show benchmark revision markers;
- a revision change creates a visual discontinuity.

Example:

```text
Sep 21  90.9
Sep 29  91.7
Oct 03  92.4
Oct 05  93.1
        ↑ same benchmark lineage

Oct 10  evaluator v3
        new lineage, not a continuation
```

---

# 16. MCB-11K — Run explorer

## Goal

Separate operational observability from result interpretation.

## Run list

Columns:

```text
run id
created/completed time
status
models
profile
planned/completed/failed
duration
benchmark lineage
git commit
```

## Run detail header

```text
status
models
cases
completed
failed
duration
suite/profile
commit
```

## Timeline hierarchy

```text
run
 ├─ model
 │   ├─ prepare
 │   ├─ capability
 │   │   ├─ dataset
 │   │   └─ cases
 │   └─ release
 └─ projection
```

Default timeline shows only meaningful lifecycle transitions.

Case-level events become visible after expansion/filtering.

## Error panel

Group failures by:

```text
runtime
dataset
request
provider
evaluation
projection
```

Show:

- count;
- first/last occurrence;
- affected model/capability;
- representative error message;
- link to cases.

---

# 17. MCB-11L — Local resource telemetry contract

## Goal

Support efficiency analysis without blocking providers that cannot report local resources.

## Sources

Preferred order:

1. runtime/Korgis native resource telemetry;
2. benchmark process/runtime sampler;
3. unavailable/null.

## Metrics

At minimum:

```text
model_prepare_ms
time_to_first_token_ms when observable
latency_ms
tokens_per_second
rss_bytes
system_ram_used_bytes
gpu_or_accelerator_memory_bytes when observable
cpu_percent
```

Sampling must be low overhead and bounded.

## Aggregation

Per execution signature/model:

- peak;
- median where meaningful;
- p95 where meaningful;
- measurement source.

Never mix resource samples from different execution signatures into one performance comparison.

## Dependency note

This workstream can integrate with future Korgis telemetry improvements. The MCB contract should accept resource telemetry even if the first implementation only populates a subset.

---

# 18. MCB-11M — Immutable share snapshots

## Goal

Freeze a benchmark story so a LinkedIn post does not change when new runs arrive.

## Snapshot creation

CLI:

```bash
uv run model-bench share create \
  --capability structured-output \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --source current
```

The snapshot resolves CURRENT results once and writes an immutable payload.

## Snapshot schema

```text
snapshot_id
created_at_utc
title
story_type
run_ids
model_signatures
benchmark_signature
execution_signatures where relevant
capability_id
dataset IDs
primary metric
paired stats
family/difficulty breakdown
efficiency values
suite/version
git commit(s)
pricing snapshot date
methodology footer
source checksums
```

The renderer reads only the snapshot, never "latest" live data.

## Snapshot immutability

- same snapshot ID never changes;
- create a new snapshot for refreshed results;
- rendered images record snapshot ID;
- snapshot JSON remains sufficient to rerender all cards.

---

# 19. MCB-11N — LinkedIn renderer

## Goal

Generate clean benchmark-native social assets, not screenshots of the full dashboard.

## Templates

Initial templates:

1. `result-comparison`;
2. `capability-deep-dive`;
3. `efficiency-comparison`;
4. `methodology`;
5. `carousel-5`.

## Default five-card story

### Card 1 — Hook

```text
Can a 2B local model
replace GPT for
structured output?
```

### Card 2 — Main result

```text
Qwen       71.7%
GPT        90.0%

delta +18.3 pp
95% CI [...]
paired n = 60
```

### Card 3 — Failure breakdown

```text
Flat
Nested
Arrays
Optional
Noisy
Adversarial
```

### Card 4 — Efficiency

Show only comparable/known values:

```text
latency
throughput
known API cost
peak RAM when available
```

### Card 5 — Methodology

```text
same paired cases
family-stratified
task/evaluator version
paired bootstrap
McNemar
suite/profile
commit
repository
```

## Renderer

Recommended path:

- dedicated React share routes/components;
- fixed aspect ratio;
- deterministic fonts/layout;
- Playwright or equivalent headless browser screenshot;
- PNG cards;
- optional PDF carousel.

The rendering pipeline must have visual regression fixtures.

## Footer

Every public card gets a compact provenance footer:

```text
MCB v2 · core · n=60 · paired benchmark · YYYY-MM-DD · snapshot <id>
```

Repository/commit may be shown on methodology card rather than every card.

---

# 20. Frontend component map

Suggested structure:

```text
dashboard/src/
├── app/
│   ├── router.tsx
│   ├── AppShell.tsx
│   └── filters.ts
├── data/
│   ├── contracts.ts
│   └── loaders.ts
├── components/
│   ├── common/
│   │   ├── MetricValue.tsx
│   │   ├── DeltaBadge.tsx
│   │   ├── EvidenceStatus.tsx
│   │   ├── ModelBadge.tsx
│   │   └── ProvenancePopover.tsx
│   ├── overview/
│   ├── capability/
│   ├── disagreements/
│   ├── model/
│   ├── run/
│   └── share/
├── pages/
│   ├── OverviewPage.tsx
│   ├── CapabilityPage.tsx
│   ├── DisagreementsPage.tsx
│   ├── ModelPage.tsx
│   ├── RunsPage.tsx
│   ├── RunPage.tsx
│   ├── ComparePage.tsx
│   ├── SharePage.tsx
│   └── ShareSnapshotPage.tsx
└── styles/
```

---

# 21. CLI target

MCB-11 should converge on:

```bash
# rebuild analytics
uv run model-bench project --rebuild

# incrementally add new runs
uv run model-bench project

# emit UI payloads
uv run model-bench dashboard-data

# build static UI
uv run model-bench dashboard-build

# create immutable share story
uv run model-bench share create \
  --capability structured-output \
  --models qwen3.5-2b-q4km,gpt-5.6-luna

# render share cards
uv run model-bench share render \
  --snapshot <snapshot-id>
```

A convenience command may later compose projection + dashboard export + build.

---

# 22. Data quality and integrity checks

Projection should reject/quarantine inconsistent evidence rather than silently repairing it.

Checks:

- manifest run_id matches folder/run records;
- case identity has one terminal latest attempt;
- completed case has raw + evaluation evidence;
- aggregate sample count can be reconciled;
- model/capability IDs exist in manifest;
- benchmark signature inputs are complete;
- paired comparisons share exact sample IDs;
- price source/date is retained when cost is known;
- share snapshot references completed projected cells;
- source checksums match projection manifest.

Expose integrity state:

```text
VALID
PARTIAL
INCONSISTENT
UNSUPPORTED_SCHEMA
```

Only VALID completed cells can be CURRENT.

---

# 23. Migration strategy for current MCB-10 runs

Do not invalidate existing evidence.

Projector migration path:

1. parse MCB-10 manifest/evidence;
2. infer missing typed event fields where safe;
3. compute signatures from persisted manifest data;
4. mark unavailable execution metadata null;
5. project as schema source `mcb10`;
6. never synthesize performance comparability when required hardware/runtime identity is absent.

Current standalone `report.html` remains supported during MCB-11.

The new dashboard becomes an additional read surface first, then can become the preferred one once parity is verified.

---

# 24. Testing strategy

## Unit/contract

- signature canonicalization;
- event validation;
- run-state derivation;
- CURRENT/HISTORICAL/STALE policy;
- comparison lineage;
- share snapshot immutability.

## Projection

Golden fixture containing:

- 2 models;
- 2 comparable successful runs;
- 1 newer partial run;
- 1 changed evaluator run;
- 1 runtime failure;
- 1 retry.

Assertions:

- correct CURRENT selection;
- partial run excluded;
- changed evaluator isolated;
- paired disagreements correct;
- rebuild == incremental projection.

## UI

- TypeScript contract compile;
- component tests for null/non-comparable states;
- route/deep-link tests;
- responsive smoke;
- dark/light mode visual checks.

## Visual regression

Golden screenshots for:

- Overview;
- Capability detail;
- Disagreement case;
- Model page;
- Run page;
- LinkedIn result card;
- five-card carousel.

## End-to-end

Fake evidence -> project -> export -> dashboard build -> share snapshot -> rendered assets.

No provider call required.

Real-provider validation remains a separate manual/local gate.

---

# 25. Performance constraints

The analytics layer should remain lightweight for local experimentation.

Initial targets:

- projector handles thousands of cases/runs without loading all raw payloads into memory;
- Overview payload remains small enough for immediate local load;
- case raw output fetched only when drilling down;
- dashboard does not ship the whole evidence corpus;
- rebuild is deterministic and can be run locally without services.

Do not add a backend service/database daemon in v1.

---

# 26. Workstream dependency graph

```text
MCB-11A Events ─────────┐
                       ├──> MCB-11D Projector ──> MCB-11E Data export
MCB-11B Signatures ─────┤                              │
                       │                              ▼
MCB-11C Latest policy ──┘                      MCB-11F UI foundation
                                                      │
                          ┌───────────────────────────┼──────────────────┐
                          ▼                           ▼                  ▼
                    11G Overview               11H Capability      11K Run explorer
                          │                           │                  │
                          │                           ▼                  │
                          │                    11I Disagreements        │
                          │                                              │
                          └──────────────┬───────────────┬───────────────┘
                                         ▼               ▼
                                    11J Model       11M Share snapshot
                                                         │
                                                         ▼
                                                   11N Renderer

11L Resource telemetry can proceed in parallel once execution signatures exist.
```

---

# 27. Parallel implementation plan

## Track A — Evidence & semantics

Can start immediately:

- MCB-11A typed events;
- MCB-11B signatures;
- MCB-11C latest policy.

These should live mostly in Python and contract tests.

## Track B — Analytics

Starts once signature/latest contracts stabilize:

- DuckDB schema;
- projector;
- derived views;
- projection manifest;
- dashboard payload exporter.

## Track C — Frontend

Can begin in parallel using frozen JSON fixtures derived from the mockup:

- React/Vite shell;
- router;
- sidebar;
- overview;
- capability page;
- model page;
- run page.

The fixture schema must match the planned dashboard export contract.

## Track D — Failure analysis

In parallel after the case payload contract:

- disagreement indexing;
- case explorer;
- raw evidence progressive disclosure.

## Track E — Sharing

Can start after capability payload shape is stable:

- share snapshot contract;
- share templates;
- fixed-size renderer;
- visual regression.

## Track F — Efficiency telemetry

Parallel after execution-signature contract:

- resource sample contract;
- Korgis/runtime adapter;
- performance aggregation;
- Model/Run UI panels.

---

# 28. Suggested delivery phases

## Phase 1 — Trustworthy cross-run data

Ship first:

- typed events;
- signatures;
- canonical latest policy;
- DuckDB projector;
- projection tests.

At the end of Phase 1 the command line can answer "what is CURRENT?" correctly.

## Phase 2 — Decision UI

Ship:

- dashboard data export;
- routes/app shell;
- Overview;
- Capability detail;
- Disagreements;
- Model profile.

At the end of Phase 2 the benchmark is usable as an analysis product.

## Phase 3 — Operational UI

Ship:

- Runs list;
- Run detail;
- timeline;
- failure grouping;
- evidence drill-down.

## Phase 4 — Shareable benchmark stories

Ship:

- immutable share snapshots;
- card templates;
- LinkedIn carousel;
- methodology/provenance footer;
- visual regression.

## Phase 5 — Efficiency enrichment

Ship:

- resource telemetry;
- execution-signature-aware performance history;
- efficiency cards.

---

# 29. Definition of Done

MCB-11 is complete when:

- [ ] raw benchmark evidence remains immutable and sufficient to rebuild analytics;
- [ ] typed event lifecycle is versioned and linked to evidence;
- [ ] model, benchmark and execution signatures are deterministic;
- [ ] CURRENT is latest valid completed comparable evidence, not simply latest timestamp;
- [ ] incomplete runs never replace valid canonical results;
- [ ] DuckDB can be rebuilt deterministically from run folders;
- [ ] incremental projection equals rebuild;
- [ ] UI uses derived typed payloads, not raw JSONL joins in the browser;
- [ ] Overview shows capability × model without an opaque overall score;
- [ ] Capability view exposes paired delta, CI, family/difficulty breakdown;
- [ ] disagreement explorer distinguishes quality disagreements from pipeline failures;
- [ ] model history never connects incompatible benchmark lineages;
- [ ] Runs UI exposes lifecycle, retries and failure stage;
- [ ] local/API efficiency semantics remain explicit;
- [ ] share snapshots are immutable and checksum/provenance backed;
- [ ] LinkedIn cards can be rendered deterministically from a snapshot;
- [ ] all key routes are deep-linkable;
- [ ] dark/light mode and responsive layouts are visually validated;
- [ ] unit/projection/UI/visual gates pass locally;
- [ ] no GitHub Actions execution is required for development validation.

---

# 30. First implementation slice

The first vertical slice should deliberately avoid implementing every screen at once.

Use one fake benchmark fixture:

```text
2 models
1 capability: structured-output
60 paired cases
6 families
2 historical runs
1 partial newer run
```

Build end-to-end:

```text
evidence
  ↓
signatures
  ↓
DuckDB
  ↓
CURRENT selection
  ↓
overview.json
  ↓
/overview
  ↓
/capabilities/structured-output
  ↓
/capabilities/structured-output/disagreements
  ↓
share snapshot
  ↓
one LinkedIn result card
```

Only after this slice is visually and semantically correct should the implementation expand to all five capabilities, full Run Explorer and five-card carousel.

This slice validates the hardest architectural decisions early:

- cross-run identity;
- comparability;
- projector correctness;
- UI data contract;
- disagreement semantics;
- share immutability.
