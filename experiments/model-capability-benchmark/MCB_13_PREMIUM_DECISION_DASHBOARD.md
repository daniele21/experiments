# MCB-13 — Premium Decision Dashboard UX/UI

Status: **PLANNED**

Depends on:

- MCB-10 vertical benchmark hardening;
- MCB-11 observability/results explorer;
- MCB-12 efficiency telemetry/share renderer.

## 1. Objective

Evolve the current MCB dashboard from a technically correct benchmark explorer into a premium **model decision product**.

The application must answer, in progressive depth:

```text
L1 — DECIDE
Which model is best for my trade-off?

        ↓

L2 — UNDERSTAND
Why is it better or worse?
Which capability/dataset drives the difference?

        ↓

L3 — DIAGNOSE
Where does it fail?
Which family, difficulty or disagreement explains the result?

        ↓

L4 — AUDIT
Can I reproduce and trust this result?
Which run, hardware, runtime, manifest and raw evidence produced it?
```

The design target is a polished production SaaS application: calm, premium, data-dense without looking crowded, and immediately understandable.

The benchmark-science contract remains stronger than the presentation layer:

```text
immutable evidence
      ↓
DuckDB projection
      ↓
typed decision payloads
      ↓
premium React UI
```

The browser must not become the source of truth.

---

## 2. Product principles

### P1 — Decision first

The default Overview must answer in 5–10 seconds:

- best quality;
- best local model;
- fastest observed model;
- lowest known API/provider cost;
- overall model ranking;
- quality × latency trade-off;
- quality × cost trade-off;
- dataset-level strengths and weaknesses.

Methodology is still visible, but below the decision layer.

### P2 — Progressive disclosure

Every view should move from summary to evidence:

```text
KPI / ranking
→ trade-off visualization
→ capability/dataset breakdown
→ failure breakdown
→ cases
→ run/provenance/raw evidence
```

Do not expose hashes, signatures or raw telemetry before they are useful.

### P3 — No opaque score

MCB may expose a benchmark-level quality index only if its aggregation policy is explicit, versioned and reproducible.

The UI must never silently average unrelated task metrics.

Target concept:

```text
Benchmark Quality Index
quality_policy_id: core-quality-v1
coverage: 5/5 capabilities · 12/12 datasets
```

The composite is an aid to navigation and ranking. Capability- and dataset-level primary metrics remain authoritative.

### P4 — Observed trade-off != strict comparability

Users need a global quality × latency view even when models run in different environments.

Therefore MCB must distinguish:

- **Observed trade-off**: descriptive view across CURRENT executions;
- **Comparable performance**: strict comparison only when performance semantics/lineage allow it.

The Overview may show observed latency across local/API executions, but must display the execution environment in tooltips/details and must not imply strict hardware-neutral comparability.

The Compare page retains the stronger compatibility guardrails.

### P5 — Local provider fee is never zero compute cost

For local models:

```text
provider_cost_usd = null
provider_cost_label = "N/A · local runtime"
```

Never put a local model at x=0 on an API/provider-cost chart.

A future compute-cost model can be added as a separate explicitly estimated semantic.

### P6 — Human-readable runtime identity

A user should see:

```text
Local · Korgis
Apple M3 Pro
arm64 · macOS
18 GB unified memory
Q4_K_M
```

before seeing an execution signature hash.

Hashes remain in provenance/technical details.

### P7 — Cross-highlighting

Selecting a model in one visualization should highlight it everywhere on the page where possible:

- leaderboard;
- scatter plots;
- dataset matrix;
- local/model detail panel.

This makes the dashboard feel like one analytical surface rather than unrelated cards.

### P8 — Premium density

Avoid oversized empty cards and avoid stacking every detail vertically.

Prefer:

- strong 12-column grid;
- compact KPI cards;
- aligned metric values;
- shared baselines;
- subtle borders/shadows;
- restrained accent colors;
- consistent spacing;
- detailed content on hover/click/accordion.

---

# 3. Information architecture

Primary navigation remains:

```text
Overview
Models
Capabilities
Compare
Runs
Share
```

New drill-down routes:

```text
/overview

/models
/models/:modelSignature

/capabilities/:capabilityId
/capabilities/:capabilityId/disagreements

/datasets/:datasetId

/compare

/runs
/runs/:runId

/share
/share/:snapshotId
```

Dataset becomes a first-class drill-down entity even if it is not a top-level sidebar item.

---

# 4. Visual system

## 4.1 App shell

Target shell:

- dark premium sidebar;
- light analytical canvas;
- sticky sidebar;
- max-width content area large enough for data visualization;
- compact top filters;
- consistent page header;
- 12-column content grid.

Desktop is the primary surface.

Responsive behavior:

- >= 1280 px: full analytical layout;
- 1024–1279 px: two-column reductions, compact sidebar;
- 768–1023 px: charts stack, tables horizontally scroll;
- < 768 px: read-focused fallback, no attempt to reproduce full desktop density.

## 4.2 Typography

Use a single modern sans-serif stack.

Hierarchy:

- page title: 28–32 px, strong weight;
- section title: 16–18 px;
- KPI value: 28–36 px;
- table/metric labels: 11–13 px;
- provenance/helper copy: 10–12 px.

Numeric values should use tabular numerals where supported.

## 4.3 Color semantics

Use color semantically, not decoratively.

Suggested stable semantics:

- primary/selection: blue-indigo;
- local deployment: green;
- API deployment: blue;
- warning/non-comparable: amber;
- failure/regression: red;
- neutral/unavailable: gray.

Model identity colors may be assigned consistently within a view, but deployment status must remain distinguishable from model color.

## 4.4 Cards

Three visual tiers:

1. **Hero KPI** — tinted background, one large decision metric;
2. **Analysis card** — white surface, chart/table;
3. **Technical detail** — neutral/compact, lower visual priority.

Avoid making every panel visually equal.

---

# 5. Data/analytics contract required by the new UI

The UI should consume precomputed summaries.

Do not aggregate large case arrays in React.

## 5.1 Quality aggregation policy

Introduce an explicit quality policy contract.

Suggested shape:

```json
{
  "quality_policy_id": "core-quality-v1",
  "label": "Core benchmark quality",
  "aggregation": "weighted_mean",
  "coverage_requirement": "complete",
  "capability_weights": {
    "intent-classification": 1.0,
    "oos-calibration": 1.0,
    "structured-output": 1.0,
    "qa-abstention": 1.0,
    "mathematical-reasoning": 1.0
  }
}
```

Each capability must define how its primary metric maps to a normalized 0–100 quality contribution.

Rules:

- transform is explicit and versioned;
- missing capability coverage is never silently treated as zero;
- incomplete coverage receives a visible PARTIAL COVERAGE state;
- ranking defaults to models satisfying the configured coverage requirement;
- underlying primary metrics are always drillable.

If the normalization policy is not yet approved, ship the premium UI with "Overall quality unavailable" rather than inventing a score.

## 5.2 Model overview summary

Add a projected model summary containing at least:

```text
model_key
model_signature
deployment
runtime_key
provider_key

quality_policy_id
overall_quality_score
quality_coverage_capabilities
quality_coverage_datasets
quality_coverage_complete

latency_p50_ms
latency_p95_ms
latency_mean_ms
observed_case_count

provider_cost_total_usd
provider_cost_per_case_usd
provider_cost_per_1k_cases_usd
provider_cost_known

input_tokens_total
output_tokens_total

failure_count
failure_rate

current_run_ids
latest_completed_at_utc
```

Latency and provider-cost aggregates must be computed from CURRENT case evidence, not from UI fixtures.

## 5.3 Capability summary

Add:

```text
model × capability
primary_metric
primary_value
normalized_quality_score
sample_count
failure_count
failure_rate
latency_p50_ms
latency_p95_ms
provider_cost_total_usd
provider_cost_per_1k_cases_usd
dataset_count
coverage_state
benchmark_signature
execution_signature
```

## 5.4 Dataset summary

Create a first-class projection:

```text
model × capability × dataset
dataset_id
sample_count
primary_metric
primary_value
normalized_quality_score
failure_count
failure_rate
latency_p50_ms
latency_p95_ms
provider_cost_total_usd
provider_cost_per_1k_cases_usd
family_count
difficulty_count
challenge_type_count
```

This projection powers the heatmaps and dataset route.

## 5.5 Human-readable execution environment

Add/project a typed execution environment entity.

Target fields:

```text
execution_signature
deployment
runtime_key
runtime_version?
provider_key

system
system_release
machine_arch
cpu_model
logical_cpu_count?
total_memory_bytes

accelerator_model?
accelerator_memory_bytes?

quantization
artifact_format
model_artifact_size_bytes?
```

Only persist privacy-safe hardware identity.

If a value is not known, leave it null.

## 5.6 Resource summary

Extend the frontend contract to expose all already-measured fields that matter:

```text
cpu_avg
cpu_peak if available
rss_avg
rss_peak
system_available_memory_min
accelerator_memory_peak
sample_count
sample_interval_ms
source
scope
sampling_error_count
```

No inferred GPU memory.

## 5.7 Pareto data

Pareto membership should be computed in analytics, not improvised in the chart component.

Produce separate semantics:

```text
observed_quality_latency_pareto
known_provider_cost_quality_pareto
```

The cost frontier contains only models with known provider cost.

---

# 6. Overview — premium decision surface

Route:

```text
/overview
```

## 6.1 Header

Show:

- Model Capability Benchmark;
- current suite/profile;
- CURRENT state;
- filters:
  - All / Local / API;
  - model selection;
  - profile;
  - optional date/history selector.

Filters should update URL query parameters.

## 6.2 KPI row

Four default KPI cards:

1. Best Quality;
2. Best Local Model;
3. Fastest Observed;
4. Lowest Known API Cost.

Each card shows:

- model name;
- main metric;
- deployment badge;
- one-line semantic label;
- optional small sparkline only if historical data actually exists.

Clicking the card selects/highlights the model.

## 6.3 Overall quality leaderboard

Primary left-side decision chart.

Show:

- rank;
- model;
- deployment badge;
- quality score;
- coverage;
- horizontal bar.

Interactions:

- click row → select model;
- secondary action → model page;
- sort/filter preserved in URL.

Partial-coverage models appear in a separate section or with a strong state label.

## 6.4 Quality × Latency

Scatter:

- y = quality;
- x = observed P50 latency;
- tooltip = P50, P95, run, deployment, runtime, hardware summary;
- highlight selected model;
- observed Pareto frontier.

Title must explicitly say **Observed quality × latency** or expose an info tooltip explaining cross-environment semantics.

## 6.5 Quality × Cost

Scatter:

- y = quality;
- x = known provider cost per 1k benchmark cases;
- only known provider-cost points are plotted;
- local models are not rendered at zero;
- empty/unknown provider cost remains N/A.

Optional toggle later:

```text
Provider cost | Estimated compute cost
```

Estimated compute cost is out of scope until a separate explicit model exists.

## 6.6 Performance by dataset

Large heatmap/table.

Hierarchy:

```text
Capability
  ↳ Dataset
```

Columns = models.

View modes:

- Score;
- Δ vs best;
- Rank.

Cell tooltip:

- primary metric;
- sample count;
- failures;
- P50/P95;
- provider cost if known;
- benchmark signature state.

Click:

```text
dataset cell → /datasets/:datasetId?model=...
```

## 6.7 Selected model detail panel

When a model is selected, show a compact side panel.

For local:

- Local / runtime;
- hardware;
- memory;
- quantization;
- P50/P95;
- RSS;
- CPU;
- accelerator memory if known.

For API:

- provider;
- endpoint/runtime identity;
- P50/P95;
- token usage;
- known provider cost.

Actions:

- Open model;
- Compare;
- View runs.

## 6.8 Methodology/provenance

Move current Overview technical cards into collapsed accordions:

- Methodology;
- CURRENT policy;
- Benchmark signatures;
- Data integrity/projection.

They remain one click away but no longer compete with the decision surface.

---

# 7. Models view

Route:

```text
/models
```

Replace the current card catalog with a sortable decision table.

Columns:

```text
Model
Deployment
Quality
Coverage
P50
P95
Provider cost / 1k cases
Failure rate
Runtime / environment
Last CURRENT result
```

Features:

- sort by any main metric;
- filter local/API;
- filter capability coverage;
- multi-select 2–4 models;
- sticky compare tray.

Click row → Model detail.

Selected rows → Compare.

---

# 8. Model detail

Route:

```text
/models/:modelSignature
```

Target sections follow the model mockup.

## 8.1 Hero KPIs

- Overall quality;
- Datasets covered;
- P50 latency;
- Peak RSS for local/runtime-backed evidence;
- Provider API cost or N/A local runtime.

## 8.2 Capability performance

Horizontal ranked bars:

- capability;
- normalized quality;
- primary metric on hover;
- optional historical delta only when same benchmark lineage.

Click capability → capability page filtered to model.

## 8.3 Execution environment

Human-readable panel.

Technical signature hashes are secondary/copyable.

## 8.4 Comparable history

Line chart grouped by compatible lineage.

Never connect incompatible benchmark lineage.

States:

- CURRENT;
- HISTORICAL;
- PARTIAL / excluded.

## 8.5 Resource telemetry

Compact metric tiles:

- CPU avg;
- CPU peak if available;
- RSS avg;
- RSS peak;
- system memory floor;
- accelerator memory;
- telemetry source;
- samples.

Do not invent missing values.

## 8.6 Dataset profile

Show:

- top-performing datasets;
- weakest datasets;
- view all datasets.

## 8.7 Representative failures

Show 2–3 case previews only.

Action → disagreement/case explorer.

---

# 9. Capability detail

Route:

```text
/capabilities/:capabilityId
```

The page answers: **why do the models differ on this capability?**

## 9.1 Hero scores

Compact per-model cards:

- capability quality;
- deployment;
- sample count;
- failures.

Paired-comparison card:

- selected pair;
- delta;
- CI;
- paired n;
- significance/practical threshold.

## 9.2 Performance by dataset

This becomes the primary analytical table.

## 9.3 Capability trade-off maps

- observed quality × latency;
- quality × known provider cost.

## 9.4 Failure breakdown

Break down by available controlled taxonomy:

- family;
- difficulty;
- challenge type.

The UI should only show dimensions actually populated for the capability.

## 9.5 Disagreement preview

Show a short list:

- A only correct;
- B only correct;
- both wrong;
- pipeline failure kept visually separate.

Action:

```text
Open disagreement explorer
```

## 9.6 Methodology details

Collapsed/lower priority:

- benchmark signature;
- primary metric;
- evaluator version;
- statistical test;
- practical delta.

---

# 10. Dataset detail

Route:

```text
/datasets/:datasetId
```

New page.

The page answers: **who wins on this dataset and why?**

Sections:

1. model ranking on dataset;
2. quality × observed latency;
3. quality × known provider cost;
4. family breakdown;
5. difficulty/challenge breakdown;
6. failures/disagreements;
7. cases;
8. methodology/provenance.

Deep-link query parameters may preselect:

```text
?model=
?capability=
?compare=
```

---

# 11. Compare view

Route:

```text
/compare
```

The Compare page is for deciding between finalists, not discovering candidates.

Support 2 models initially; component contract should allow up to 4 later.

## 11.1 Selection header

- capability selector;
- Model A;
- Model B;
- Add model;
- compatibility state.

Selections live in URL query params.

## 11.2 Hero summaries

Per model:

- quality;
- P50;
- provider cost / 1k cases;
- failure rate;
- deployment.

Delta card:

- quality delta;
- latency delta;
- cost delta;
- failure-rate delta.

Delta metrics must carry semantic state:

- comparable;
- observed-only;
- unavailable.

## 11.3 Side-by-side metrics

Shared bars for:

- overall/capability quality;
- P50;
- P95;
- provider cost;
- input/output tokens;
- failure rate;
- coverage.

Normalize bar lengths per metric only; never imply cross-unit comparison.

## 11.4 Trade-off maps

Show selected models highlighted and all other eligible models faded.

## 11.5 Dataset differential table

Columns:

```text
Dataset | A | B | Δ
```

Sort by:

- largest A advantage;
- largest B advantage;
- smallest gap;
- hardest dataset.

## 11.6 Efficiency semantics card

Explicitly explain:

```text
Quality comparable
Efficiency observed / partially comparable
```

or:

```text
Quality comparable
Efficiency comparable
```

depending on lineage/semantics.

Do not hide non-comparability.

## 11.7 Sticky compare tray

When models are selected:

- keep a bottom tray visible;
- show selected models;
- add/remove model;
- open comparison.

This component should also be reusable from Overview and Models.

---

# 12. Runs view

Runs remains operational/audit-oriented.

Do not turn it into another decision dashboard.

Enhancements:

- stronger status hierarchy;
- compact summary before timeline;
- link from run/model/capability cells back to analytical views;
- environment summary on run detail;
- resource timeline expandable;
- typed failures grouped first, raw events after expansion.

Default Run view:

```text
summary
→ failures
→ resources
→ lifecycle
→ raw event detail
```

instead of leading with raw lifecycle chronology.

---

# 13. Share view

Retain the immutable snapshot architecture from MCB-12.

Align visual language with the premium application:

- same typography;
- same model colors;
- same metric formatting;
- same deployment badges;
- same semantics for unknown/non-comparable values.

Do not screenshot dashboard pages for social cards.

Share assets remain dedicated snapshot-only compositions.

---

# 14. Interaction design

## 14.1 Global filters

Filters should use URL state.

Suggested query params:

```text
deployment=all|local|api
models=a,b,c
profile=core
quality_policy=core-quality-v1
selected_model=...
view=score|delta|rank
```

Refreshing/deep-linking must preserve the analytical state.

## 14.2 Tooltips

Tooltips should answer semantics, not merely repeat values.

Example latency tooltip:

```text
P50 latency: 418 ms
P95 latency: 836 ms
Execution: Local · Korgis
Hardware: Apple M3 Pro · 18 GB
Cases: 468

Observed across this execution environment.
```

## 14.3 Unknown state

Use:

- — for unavailable;
- N/A + reason in tooltip;
- never coerce null to zero.

## 14.4 Non-comparable state

Use amber semantic chip and explanatory text.

Do not gray out quality if quality is comparable but efficiency is not.

## 14.5 Loading

The dashboard is primarily static/exported data, but components should support skeleton loading for future live data sources.

Avoid spinners that shift layout.

---

# 15. Frontend refactor

The current `dashboard/src/App.tsx` is a monolithic file and should not absorb MCB-13.

Target structure:

```text
dashboard/src/
├── app/
│   ├── AppShell.tsx
│   ├── router.ts
│   ├── routes.tsx
│   ├── queryState.ts
│   └── navigation.ts
├── components/
│   ├── common/
│   │   ├── PageHeader.tsx
│   │   ├── MetricCard.tsx
│   │   ├── MetricValue.tsx
│   │   ├── DeploymentBadge.tsx
│   │   ├── EvidenceState.tsx
│   │   ├── CompatibilityBadge.tsx
│   │   ├── EmptyMetric.tsx
│   │   └── MethodologyAccordion.tsx
│   ├── charts/
│   │   ├── QualityBarRanking.tsx
│   │   ├── TradeoffScatter.tsx
│   │   ├── HistoryLineChart.tsx
│   │   ├── ComparisonBars.tsx
│   │   └── MiniSparkline.tsx
│   ├── tables/
│   │   ├── DatasetHeatmap.tsx
│   │   ├── ModelLeaderboard.tsx
│   │   └── DatasetDeltaTable.tsx
│   ├── model/
│   ├── capability/
│   ├── compare/
│   ├── run/
│   └── share/
├── pages/
│   ├── OverviewPage.tsx
│   ├── ModelsPage.tsx
│   ├── ModelPage.tsx
│   ├── CapabilityPage.tsx
│   ├── DatasetPage.tsx
│   ├── ComparePage.tsx
│   ├── RunsPage.tsx
│   ├── RunPage.tsx
│   └── SharePage.tsx
├── data/
│   ├── contracts.ts
│   ├── loaders.ts
│   └── fixtures/
├── styles/
│   ├── tokens.css
│   ├── globals.css
│   ├── layout.css
│   └── components.css
└── types.ts
```

The exact filenames may change, but page-level logic must leave `App.tsx`.

---

# 16. Charting implementation

The current hand-built bars are sufficient for small breakdowns but not for the new decision surface.

Adopt one lightweight charting layer for:

- scatter;
- line/history;
- optional tooltips/cross-highlighting.

Requirements:

- deterministic rendering;
- no canvas-only dependency if it harms screenshot rendering;
- accessible labels/tooltips where practical;
- export-safe in Chrome headless;
- no network dependency.

Do not add a heavy visualization framework merely to draw bars.

Simple bars/heatmaps should remain CSS/DOM.

Pareto frontier calculation remains in Python analytics; frontend only renders the projected frontier/membership.

---

# 17. Backend/analytics changes

Primary files expected to change:

```text
src/model_capability_bench/analytics/projector.py
src/model_capability_bench/analytics/dashboard_export.py
src/model_capability_bench/analytics/latest.py
dashboard/src/types.ts
dashboard/src/...
```

Potential new analytics modules:

```text
analytics/quality_index.py
analytics/efficiency.py
analytics/pareto.py
analytics/datasets.py
```

Keep aggregation logic unit-testable outside DuckDB SQL where useful.

---

# 18. Workstreams

## MCB-13A — Visual foundation & component system

Can start immediately in parallel using fixtures.

Deliver:

- premium shell;
- design tokens;
- page headers;
- metric cards;
- badges;
- accordions;
- sticky compare tray;
- responsive grid;
- fixture-based Storybook-like/demo routes if useful.

No analytics dependency.

### DoD

- shared visual primitives replace repeated one-off CSS;
- sidebar/header match premium target;
- desktop layout stable at 1440/1600 widths;
- null/warning/local/API states have consistent visuals.

---

## MCB-13B — Decision analytics projection

Starts immediately in Python.

Deliver:

- explicit quality aggregation policy;
- model overview summary;
- capability summary;
- dataset summary;
- P50/P95 latency aggregation;
- known provider cost aggregation;
- failure-rate aggregation;
- observed Pareto membership;
- human-readable execution environment projection.

### DoD

- rebuildable from immutable run evidence;
- no React aggregation dependency;
- null cost remains null;
- incomplete quality coverage explicit;
- deterministic golden fixture.

---

## MCB-13C — Overview decision surface

Depends on 13A + stable 13B contract.

Deliver:

- KPI row;
- leaderboard;
- quality × latency;
- quality × cost;
- dataset heatmap;
- selected-model detail;
- collapsed methodology/provenance.

### DoD

A user can identify the strongest overall, local, fast and low-known-cost candidates without visiting another route.

---

## MCB-13D — Capability + Dataset drill-down

Can proceed partly with fixtures in parallel with 13C.

Deliver:

- premium Capability view;
- dataset heatmap;
- failure family/difficulty/challenge breakdown;
- disagreement preview;
- new Dataset route.

### DoD

Every Overview heatmap cell can drill into an explanatory dataset/capability surface.

---

## MCB-13E — Model profile

Depends on 13A + execution-environment contract from 13B.

Deliver:

- hero KPIs;
- capability performance;
- human-readable runtime/hardware;
- comparable history;
- resource telemetry;
- dataset profile;
- representative failures.

### DoD

A local model page explains both **how good it is** and **where/how it ran** without exposing hashes as the primary identity.

---

## MCB-13F — Compare decision workspace

Depends on 13A + 13B.

Deliver:

- URL-backed model selection;
- two-model hero;
- delta card;
- comparison bars;
- contextual trade-off maps;
- dataset delta table;
- efficiency semantics;
- sticky compare tray.

### DoD

The page makes quality/latency/cost trade-offs legible without overstating performance comparability.

---

## MCB-13G — Runs/Share integration

Mostly independent once shared components exist.

Deliver:

- Runs hierarchy polish;
- analytical backlinks;
- execution environment summary;
- share visual alignment;
- consistent metric formatting.

### DoD

Operational/audit routes feel part of the same product without competing with the decision surfaces.

---

## MCB-13H — Visual QA, accessibility & performance

Runs throughout, final gate after C–G.

Deliver:

- Playwright route screenshots;
- visual regression;
- keyboard/focus smoke;
- responsive screenshots;
- empty/null/non-comparable fixtures;
- large model/dataset stress fixture;
- Chrome headless rendering gate.

### DoD

Premium appearance is protected by deterministic automated checks.

---

# 19. Dependency graph

```text
                 ┌─────────────── MCB-13A Visual foundation ───────────────┐
                 │                                                        │
                 │                                                        ▼
MCB-11/12 ──> MCB-13B Decision analytics ───────┬──> 13C Overview
                                                 ├──> 13D Capability/Dataset
                                                 ├──> 13E Model
                                                 └──> 13F Compare
                                                           │
13A ────────────────────────────────────────────────────────┤
                                                           ▼
                                                   13G Runs/Share
                                                           │
                                                           ▼
                                                   13H Visual QA
```

13A and 13B are the two first parallel tracks.

13D can begin with frozen fixtures before 13B is complete.

---

# 20. Delivery phases

## Phase 0 — Freeze UX contract

- commit MCB-13 plan;
- capture target route list;
- create fixture contracts matching the mockups;
- define quality-index policy decision;
- define metric formatting rules.

Exit criterion:

- frontend and analytics teams can work without reinterpreting the mockups.

## Phase 1 — Foundation

Parallel:

**Frontend**
- refactor App.tsx;
- tokens;
- shell;
- shared components;
- chart primitives.

**Analytics**
- summary projections;
- quality policy;
- latency/cost percentiles;
- dataset aggregates;
- environment projection.

Exit criterion:

- typed JSON fixtures and real export use the same schema.

## Phase 2 — Overview first

Implement Overview end-to-end.

This is the highest-priority route.

Exit criterion:

- all top-level decision questions are answered on one screen;
- selected model cross-highlights;
- local/API semantics are correct.

## Phase 3 — Explain

Implement:

- Capability;
- Dataset;
- Model.

Exit criterion:

- every high-level number can be explained through a drill-down.

## Phase 4 — Compare

Implement the dedicated final-decision workflow.

Exit criterion:

- two finalists can be compared across quality, dataset performance, latency, cost, failures and runtime semantics.

## Phase 5 — Operational polish

Implement:

- Runs hierarchy improvements;
- Share visual alignment;
- methodology/provenance accordions.

## Phase 6 — Hardening

- responsive;
- accessibility;
- stress data;
- visual regression;
- performance;
- deterministic Chrome screenshots.

---

# 21. Recommended implementation order

Concrete sequence:

1. create new typed UI payload contract v2;
2. implement analytics summaries with fixture/golden tests;
3. split `App.tsx` into shell/pages/shared components;
4. implement design tokens and premium shell;
5. implement Overview with fixture data;
6. connect Overview to real exported payload;
7. implement Model detail;
8. implement Capability detail;
9. implement Dataset detail;
10. implement Compare;
11. polish Runs;
12. align Share components;
13. visual regression + responsive + accessibility;
14. remove obsolete fixture-only code and duplicated CSS.

Do not attempt all pages before validating the new Overview with real projected data.

---

# 22. Testing strategy

## 22.1 Python analytics

Unit tests:

- quality normalization;
- coverage rules;
- latency P50/P95;
- cost aggregation;
- null cost;
- dataset aggregation;
- failure rate;
- Pareto membership;
- execution environment null handling.

Projection golden:

```text
5 models
3 capabilities
8 datasets
local + API
known + unknown cost
compatible + different executions
partial coverage
partial newer run
resource telemetry present + absent
```

Assertions:

- CURRENT policy unchanged;
- no partial run replaces valid CURRENT;
- quality score requires declared policy;
- local cost stays null;
- P50/P95 deterministic;
- dataset totals reconcile to cases;
- environment metadata is privacy-safe.

## 22.2 Frontend contracts

- TypeScript compile;
- schema fixture compatibility;
- no implicit `any` for decision payloads;
- formatters tested for null/unknown/non-comparable.

## 22.3 Component tests

At minimum:

- MetricCard;
- DeploymentBadge;
- CompatibilityBadge;
- TradeoffScatter tooltip/state;
- DatasetHeatmap;
- ModelLeaderboard;
- StickyCompareTray;
- MethodologyAccordion.

## 22.4 Route tests

- deep links load;
- query-state preserved;
- model selection works;
- compare selections survive refresh;
- cell drill-down routes correctly.

## 22.5 Visual regression

Golden desktop screenshots:

- Overview;
- Models;
- Model detail local;
- Model detail API;
- Capability;
- Dataset;
- Compare comparable;
- Compare partially comparable;
- Runs;
- Run detail;
- Share.

State screenshots:

- no cost;
- no resource telemetry;
- partial coverage;
- non-comparable performance;
- empty history.

## 22.6 Responsive

Golden screenshots at:

- 1600×1000;
- 1440×900;
- 1280×800;
- 1024×768;
- mobile read fallback.

## 22.7 Performance

Targets for local static dashboard:

- Overview JSON remains bounded and excludes raw case payloads;
- raw case evidence loads only on drill-down;
- no full evidence corpus embedded in page;
- charts render without blocking interaction on expected model counts;
- dataset table virtualizes only if real volume requires it.

---

# 23. Acceptance criteria by page

## Overview

- no technical hash visible above the fold;
- four decision KPIs;
- quality leaderboard;
- latency and cost trade-off maps;
- dataset heatmap;
- selected-model detail;
- methodology collapsed;
- local cost not shown as zero.

## Model

- quality and coverage obvious immediately;
- local hardware/runtime readable in plain language;
- history lineage-safe;
- telemetry null-safe;
- top/weak datasets visible.

## Capability

- model ranking visible immediately;
- dataset differences explain aggregate result;
- family/difficulty breakdown available;
- paired comparison statistically grounded;
- disagreements one click away.

## Dataset

- ranking + trade-off + breakdown + cases;
- direct deep link from Overview/Capability.

## Compare

- selected models obvious;
- deltas obvious;
- quality comparability separated from efficiency semantics;
- dataset delta table;
- other models provide context without dominating.

## Runs

- summary/failures before raw event detail;
- clear links back to analytical views.

---

# 24. Non-goals

MCB-13 does **not**:

- introduce a backend service;
- make DuckDB the source of truth;
- compute benchmark statistics in the browser;
- assign local provider cost = 0;
- infer GPU/accelerator memory;
- connect incompatible benchmark histories;
- hide non-comparable efficiency;
- replace task-specific primary metrics with the quality index;
- redesign the benchmark science itself;
- require provider calls to render the dashboard.

---

# 25. Definition of Done

MCB-13 is complete when:

- [ ] the dashboard looks and behaves like one coherent premium product rather than a collection of benchmark pages;
- [ ] Overview is a decision surface with quality, latency, cost and dataset-level analysis;
- [ ] an explicit versioned quality aggregation policy powers any overall score;
- [ ] incomplete coverage is visible and cannot silently rank as complete;
- [ ] P50/P95 latency is projected from case evidence;
- [ ] known provider cost is aggregated consistently;
- [ ] local provider cost remains null/N/A;
- [ ] observed cross-environment trade-offs are distinguished from strict performance comparability;
- [ ] human-readable runtime/hardware identity is projected and visible for local runs;
- [ ] dataset is a first-class drill-down;
- [ ] Model page exposes quality + execution environment + telemetry + history;
- [ ] Capability page explains aggregate score via datasets and controlled failure dimensions;
- [ ] Compare exposes quality/latency/cost/failure trade-offs and semantic compatibility;
- [ ] Runs stays operational/audit-oriented;
- [ ] methodology/provenance is available through progressive disclosure;
- [ ] selection/filter state is deep-linkable;
- [ ] App.tsx is decomposed into maintainable pages/components;
- [ ] dashboard payloads remain typed and projection-driven;
- [ ] visual regression protects all primary routes and semantic states;
- [ ] real Chrome screenshot gates pass;
- [ ] no provider call is needed for UI tests/builds;
- [ ] the premium Overview is validated first against real projected benchmark data before expanding further.

---

# 26. First implementation slice

Do **not** start by rebuilding every route.

The first slice should be:

```text
real immutable evidence
        ↓
DuckDB
        ↓
overview summary v2
        ↓
Overview premium UI
```

Fixture:

```text
4–5 models
local + API
3 capabilities minimum
6–8 datasets
known API cost for at least 2 models
local cost null
latency for all models
resource telemetry for at least 1 local model
one partial newer run
```

Implement only:

1. premium shell;
2. KPI row;
3. overall quality leaderboard;
4. observed quality × latency;
5. known-provider-cost × quality;
6. performance-by-dataset heatmap;
7. selected-model detail;
8. methodology/provenance accordion.

If this first screen does not make the benchmark understandable in seconds, do not expand to the other views yet.

This slice validates the most important product decision of MCB-13: turning trustworthy benchmark evidence into a fast, premium model-selection experience.
