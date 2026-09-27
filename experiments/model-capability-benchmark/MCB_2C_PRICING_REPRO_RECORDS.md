# MCB-2C — Pricing, Reproducibility and Evidence Records

Status: **COMPLETE** — focused pricing/reproducibility gate green (24/24) and full Jev characterization suite green (51/51).

MCB-2C extracts the remaining low/medium-coupling primitives needed before transport
refactoring: token pricing math, deterministic selection/fingerprinting, and the generic
evidence record model.

## 1. Shared pricing primitives

New module:

- `benchmark_core.pricing`.

It owns:

- `TokenPrices`;
- cached/uncached input token cost calculation;
- output token cost calculation;
- JSON pricing snapshot loading;
- generic pricing snapshot metadata extraction.

The mapping from a Jev provider/model to a concrete pricing key remains inside
`jev_bench.costs`, because rules such as `provider == "jev"` and the `jev*` model
prefix are suite/provider-specific.

The resulting dependency is:

```text
Jev provider/model rule
        ↓
TokenPrices
        ↓
benchmark_core.estimate_token_cost_usd
```

Existing `jev_bench.costs.estimate_cost_usd` and `pricing_metadata` APIs are preserved.

## 2. Shared reproducibility primitives

New module:

- `benchmark_core.reproducibility`.

It owns:

- isolated seeded Python RNG creation;
- ordered SHA-256 selection fingerprints.

BANKING77 and CLINC150 sampling now use the shared seeded RNG while preserving Python
`random.Random(seed)` semantics exactly.

The contract test freezes both:

- the shuffled order for a known seed;
- the SHA-256 fingerprint of that ordered selection.

Dataset-specific balancing/filtering remains in Jev until the dataset registry workstream.

## 3. Generic evidence data model

New contracts:

- `RawInferenceRecord`;
- `EvaluationRecord`;
- `AggregateMetricRecord`.

These explicitly implement the three layers already defined in the implementation plan:

```text
raw inference evidence
        ↓
task evaluation
        ↓
aggregate metric
```

### RawInferenceRecord

Carries observable provider/runtime evidence:

- run/group/suite/task/sample identity;
- provider/model identity;
- raw and normalized outputs;
- latency;
- token usage;
- estimated API cost;
- validity;
- typed error kind/message;
- metadata.

It can be constructed directly from `InferenceResult`.

### EvaluationRecord

Carries task-level semantics:

- task/sample identity;
- evaluator version;
- expected and predicted values;
- per-case metrics;
- validity/error;
- metadata.

It can be constructed from `TaskResult`.

### AggregateMetricRecord

Carries reporting-ready aggregates without assuming accuracy as the only metric:

- model;
- task;
- metric name/value;
- sample count;
- failure count;
- optional dataset/profile;
- metadata.

## 4. What deliberately stays Jev-specific

MCB-2C does **not** extract the current dashboard leaderboard logic.

The existing Jev reporting layer contains assumptions such as:

- numbered experiment tags (`01-routing`, `02-calibration`, ...);
- accuracy-based ordering;
- "leader", "fastest", and "sweet spot" badges;
- specific latency thresholds;
- Jev/Korgis display-label rules.

Those are presentation/policy choices for the existing experiment, not generic benchmark
core contracts.

The generic record model is the stable boundary that MCB-8 can later use to build a
capability matrix without inheriting those assumptions.

## 5. Deferred after MCB-2C

The main remaining MCB-2 extraction is transport/error-policy work:

- reusable OpenAI-compatible HTTP transport;
- generic OpenAI transport where useful;
- runtime-independent transport error normalization;
- retry/timeout policy hooks.

Prompt construction, bounded decision parsing and Jev question semantics must remain in
`jev-vs-llm`.

## Definition of Done

- [x] generic token-cost math exists;
- [x] Jev cost API delegates to shared pricing math;
- [x] pricing snapshot loading/metadata is shared;
- [x] deterministic RNG helper exists;
- [x] public dataset sampling uses the shared RNG without changing semantics;
- [x] selection fingerprinting exists with a golden contract;
- [x] raw/evaluation/aggregate record contracts exist;
- [x] leaderboard/dashboard-specific policy remains outside benchmark-core;
- [x] focused Ruff/compile checks pass;
- [x] pricing and public-data compatibility tests pass (24/24 focused suite);
- [x] MCB-1/2A/2B gates remain green;
- [x] full Jev characterization suite remains green (51/51).
