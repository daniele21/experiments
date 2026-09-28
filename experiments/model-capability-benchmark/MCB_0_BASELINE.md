# MCB-0 — Jev vs LLM Baseline and Extraction Map

Status: **COMPLETE** — focused Ruff gate green and full Jev pytest suite green (46/46).

This document freezes the observable contracts that must remain stable while the shared
`benchmark-core` is extracted from `jev-vs-llm`.

## 1. Current entrypoints

The current experiment exposes three relevant execution paths:

1. `jev-bench` via `src/jev_bench/cli.py`;
2. `scripts/run_local_matrix.py` for autonomous Korgis local model matrices;
3. `scripts/run_clm_matrix.py` for CLM runs on the same decision harness.

The reusable core must eventually serve all three paths without forcing Jev-specific
semantics into generic model benchmarking.

## 2. Characterized smoke-suite contract

With `scaling_repeats=1`, the committed smoke suite currently emits:

| Experiment | Rows | Primary rows | Meaning |
|---|---:|---:|---|
| `01-routing` | 24 | 24 | one routing decision per case |
| `02-calibration` | 30 | 30 | 24 clear + 6 ambiguous cases |
| `03-parallel-scaling` | 6 | 0 | one batch row for 1/2/4/8/16/32 questions |
| `04-workflow` | 30 | 6 | 4 intermediate decisions + one final action per case |
| `05-hybrid-agent` | 25 | 5 | 4 intermediate decisions + one final action per case |

Total: **115 rows**.

The characterization provider returns the expected intermediate decisions for committed
smoke fixtures, so all primary decision rows are expected to remain correct. This protects
workflow composition as well as simple classification.

## 3. Current result-row contract

The shared runner currently persists these common fields:

- `experiment`;
- `case_id`;
- `input_state`;
- `provider`;
- `model`;
- `question_id`;
- `expected`;
- `actual`;
- `correct`;
- `confidence`;
- `predicted_probability`;
- `latency_ms`;
- `input_tokens`;
- `cached_input_tokens`;
- `output_tokens`;
- `estimated_cost_usd`;
- `valid`;
- `error`;
- `primary_metric`.

Experiment-specific fields currently include:

- `decision_trace` for workflow/agent final actions;
- `question_count` for parallel scaling;
- dataset metadata such as `difficulty`, `dataset`, `dataset_revision`,
  `source_split`, and `benchmark_tier` for public runs.

Two failure contracts are explicitly protected:

1. a provider-level invalid result becomes one `__request__` row;
2. a valid provider result missing one expected answer becomes an invalid row for that
   specific question with `error = "missing answer"`.

## 4. Persistence contract

`append_results` is currently append-only at CSV level:

```text
new frame
   +
existing CSV (if present)
   ↓
combined CSV
```

The generic core may later replace CSV internals, but compatibility adapters must preserve
append semantics for existing Jev commands until migration is complete.

## 5. Manifest contract

`write_manifest` currently records:

- run group;
- suite;
- UTC creation timestamp;
- runner location;
- git commit;
- Python/platform identity;
- requested models;
- resolved models;
- parameters;
- pricing snapshot;
- relevant package versions.

This is the minimum compatibility contract for the extraction. MCB-1/2 may extend the
manifest with task, prompt, dataset, model artifact and runtime identities, but must not
silently remove the existing provenance.

## 6. Extraction classification

### Generic — extract with minimal semantic change

| Component | Current location | Target |
|---|---|---|
| run manifest writing | `jev_bench/manifest.py` | `benchmark_core.manifests` |
| cost helpers | `jev_bench/costs.py` | `benchmark_core.pricing` |
| common result persistence | runner/CLI helpers | `benchmark_core.persistence` |
| report data plumbing | report/reporting modules | `benchmark_core.reporting` |
| run identity/tagging | CLI helpers | `benchmark_core.runner` |
| seed/reproducibility utilities | dataset/runner helpers | `benchmark_core` |
| common telemetry fields | provider results | generic inference result |

### Generic after adaptation — refactor, then extract

| Component | Why adaptation is required |
|---|---|
| OpenAI provider transport | currently returns Jev `Decision` objects |
| Korgis provider transport | prompt/parser are bounded-decision-specific |
| CLM provider transport | provider lifecycle is reusable, output contract is not |
| MiniCPM API transport | transport is reusable, decision parsing is specialized |
| public dataset cache/download | currently knows BANKING77/CLINC150 directly |
| matrix orchestration | currently assumes decision experiments and Korgis lifecycle |
| report generation | currently assumes accuracy/calibration-oriented schemas |

### Jev-specific — keep in `jev-vs-llm`

- `DecisionProvider`;
- `QuestionSpec`;
- `Decision`;
- `choice`, `noul`, `score` semantics;
- Jev provider;
- routing/calibration smoke fixtures;
- expense workflow policy;
- support-agent policy;
- deterministic final-action functions;
- decision-specific parsing and validation.

## 7. Existing tests already protecting useful behavior

The repository already contains coverage for:

- Korgis provider behavior;
- CLM provider and runner;
- MiniCPM provider;
- cost calculations;
- metric calculations;
- report rendering;
- model-matrix parsing;
- public dataset balancing/filtering;
- selected runner behavior.

MCB-0 adds missing cross-cutting characterization coverage rather than replacing these
tests.

## 8. Dataset reproducibility baseline

BANKING77 and CLINC150 are pinned to explicit upstream revisions in
`benchmark_data.py`. Sampling is seed-based and must remain deterministic during the
dataset-registry migration.

A same-seed fixture test is part of MCB-0 so later adapters cannot silently change selected
sample order/content.

## 9. Known architectural debt intentionally not fixed in MCB-0

MCB-0 is a safety layer, not the refactor itself. These remain targets for later work:

- experiment dispatch uses `if/elif`;
- public profiles live in Python;
- decision provider combines transport + prompt + parsing;
- local model configuration contains machine-specific paths;
- local and CLM execution have separate orchestration entrypoints;
- CSV rows do not preserve generic raw inference output;
- result schema is centered on `correct/valid`;
- dataset loading is coupled to specific public datasets;
- reporting assumes current Jev-oriented task families.

These are migration inputs for MCB-1 through MCB-8, not reasons to mutate behavior now.

## 10. MCB-0 closure criteria

MCB-0 can be marked complete when:

- [x] current entrypoints are documented;
- [x] extraction candidates are classified;
- [x] smoke-suite row counts are characterized;
- [x] primary workflow outputs are characterized;
- [x] invalid-provider and missing-answer behavior are characterized;
- [x] persistence append behavior is characterized;
- [x] manifest schema is characterized;
- [x] public dataset same-seed reproducibility is tested;
- [x] focused Ruff gate passes on MCB-0 characterization/test files;
- [x] full Jev pytest suite passes in CI (46/46).

The legacy repository-wide `ruff check .` workflow still reports pre-existing lint debt in
production/support files outside MCB-0. That debt is tracked separately and is not caused
by this workstream. MCB-1 may now begin changing production contracts behind the protected
baseline.
