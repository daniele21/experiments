# MCB-8 — Capability Reporting

Status: **COMPLETE**.

MCB-8 adds a neutral reporting layer on top of the persisted MCB-7 evidence artifacts.
Rendering a report never invokes a model, provider, runtime or evaluator.

## Reporting contract

The report is derived only from:

```text
run_manifest.json
aggregates.jsonl
report_index.jsonl
raw.jsonl
evaluation.jsonl
events.jsonl
```

`run_manifest.json` identifies the active `run_id`, ordered model list and ordered
capability list.

`report_index.jsonl` is the bridge between aggregate metrics and drill-down evidence.
Every entry pins the exact `case_id + attempt` pairs used for one model × capability
cell. This prevents a later retry or `--no-resume` execution from silently changing a
historical report.

## Main view

The primary view is a capability × model matrix.

Each cell shows only:

- the capability's declared primary metric;
- sample count;
- pipeline failure count.

The report deliberately does not calculate:

- an overall model score;
- a model ranking;
- a winner;
- leader/fastest/sweet-spot badges.

Different capabilities therefore remain separate measurements instead of being collapsed
into an opaque aggregate.

## Secondary metrics

Each capability has a dedicated metric table showing all persisted aggregate metrics for
each model, including where configured:

- quality;
- invalid-output rate;
- latency p50/p95;
- token usage;
- estimated API/provider cost.

Missing evidence is rendered as unavailable rather than zero.

## Cost semantics

The report preserves three different states:

```text
known provider/API cost > 0
known provider/API fee = 0
unknown provider/API cost = null
```

A local provider fee of zero does not mean local execution has zero hardware, energy or
amortisation cost.

Those resource metrics remain separate dimensions for future local-resource telemetry.

## Drill-down

Every model × capability section exposes case evidence through collapsible HTML details.

Case rows show:

- sample id;
- dataset id;
- exact case id and attempt;
- expected value;
- prediction;
- inference validity;
- evaluation validity;
- latency;
- typed inference/evaluation error;
- normalized provider output;
- raw provider evidence.

The number of rendered case rows per cell is configured by
`reporting.max_case_rows_per_cell`.

Truncation only affects HTML/report payload size. Aggregate metrics are still based on the
full indexed evidence set.

## Infrastructure events

Runtime and lifecycle events are shown in a separate section.

Examples:

- run started/completed;
- runtime prepare failure;
- runtime release failure;
- dataset loading failure.

These are not mixed into model-quality measurements.

## Configuration

Authoritative defaults live in `reporting.yaml`:

```yaml
reporting:
  title: Model Capability Benchmark
  html_filename: report.html
  json_filename: report.json
  numeric_precision: 4
  max_case_rows_per_cell: 100
```

The loader is strict and rejects unknown keys.

`reporting.yaml` is included in the run manifest SHA-256 configuration checksums.

## Outputs

A completed run directory contains:

```text
state.jsonl
raw.jsonl
evaluation.jsonl
aggregates.jsonl
report_index.jsonl
events.jsonl
environment.json
run_manifest.json
report.json
report.html
```

`report.json` is the machine-readable report model.

`report.html` is standalone and requires no external frontend runtime or service.

## Automatic report generation

`model-bench run` renders both report artifacts after the run manifest is written.

Example:

```bash
uv run model-bench run \
  --run-group capability-smoke \
  --models qwen3.5-2b-q4km,gpt-5.6-luna \
  --capabilities structured-output,mathematical-reasoning \
  --profile smoke
```

The CLI output includes the report paths.

## Artifact-only rendering

A persisted run can be rendered again without any provider credentials or runtime:

```bash
uv run model-bench report \
  --run-dir results/runs/capability-smoke
```

Custom output locations are supported:

```bash
uv run model-bench report \
  --run-dir results/runs/capability-smoke \
  --html /tmp/capability-report.html \
  --json /tmp/capability-report.json
```

The report command is handled before model registry/runtime setup. It therefore does not
require:

- `OPENAI_API_KEY`;
- `KORGIS_BASE_URL`;
- `MINICPM_API_KEY`;
- a running Korgis server.

## Modular implementation

The reporting package is intentionally split by responsibility:

```text
reporting/
├── config.py         strict reporting config
├── model.py          report domain model
├── evidence.py       persisted artifact lookup + exact case attempts
├── data.py           report composition
├── html_format.py    escaping/value formatting
├── html_cases.py     case drill-down
├── html_sections.py  matrix/metric/event sections
├── html_style.py     standalone CSS
├── html.py           renderer composition
└── export.py         HTML/JSON output
```

This keeps report loading, domain logic and presentation independently testable.

## Automated validation

The MCB-8 gate verifies:

- strict reporting config;
- current run-id filtering;
- last-write aggregate/index semantics;
- exact `case_id + attempt` drill-down;
- an unindexed later attempt cannot leak into the report;
- unknown cost remains `null`;
- missing model/capability evidence remains unavailable;
- case truncation;
- standalone HTML + JSON export;
- absence of ranking/winner/badge semantics;
- report rendering with no provider environment;
- MCB-7 report-index regression.

All cumulative MCB gates remain part of the merge criteria.

## Definition of Done

- [x] model × capability primary-metric matrix;
- [x] secondary metric tables;
- [x] exact case drill-down to raw/evaluation evidence;
- [x] infrastructure events separated from quality;
- [x] unknown/zero cost semantics remain distinct;
- [x] no mandatory overall score or ranking;
- [x] standalone HTML report;
- [x] machine-readable JSON report;
- [x] report rendering is provider/runtime independent;
- [x] reporting configuration is declarative and provenance-tracked;
- [x] MCB-8 and cumulative regression gates are green.
