# MCB-12 — Efficiency Telemetry & Share Renderer

Status: **PLANNED**

Depends on:

- MCB-10 vertical benchmark hardening;
- MCB-11 observability/results explorer core.

## Objective

Complete the enrichment layer that should not block the benchmark analytics core:

1. capture resource usage for local/runtime-backed inference;
2. preserve resource semantics inside execution lineage;
3. expose comparable efficiency signals in Model, Run and Compare views;
4. render immutable share snapshots into deterministic LinkedIn-ready PNG/PDF assets;
5. add visual regression coverage for public cards.

The source-of-truth rule remains unchanged:

```text
immutable run evidence
      ↓
analytics projection
      ↓
share snapshot
      ↓
deterministic renderer
```

Rendered images are outputs, never benchmark evidence.

## 1. Resource telemetry contract

Add an optional typed resource sample/summary contract with null-safe fields such as:

```text
cpu_percent_avg
cpu_percent_peak
rss_mb_avg
rss_mb_peak
system_memory_mb_peak
gpu_or_accelerator_memory_mb_peak
energy_joules
power_watts_avg
sample_count
sample_interval_ms
source
scope
```

Rules:

- unavailable metrics stay null;
- provider fee = 0 never implies compute cost = 0;
- resource metrics are comparable only inside compatible execution signatures;
- runtime-reported values retain their source and sampling semantics;
- benchmark code must not guess GPU/accelerator memory from process RSS.

## 2. Korgis/runtime integration

Prefer runtime-native telemetry when Korgis exposes it.

The benchmark adapter should:

- capture a baseline before model activation when available;
- capture inference-window samples or runtime summaries;
- attach model/runtime identity to each sample;
- persist raw telemetry separately from derived summaries;
- tolerate runtimes that expose no telemetry;
- never make quality evaluation fail solely because telemetry is unavailable.

Fallback process-level telemetry may be added only when ownership of the measured process is explicit.

## 3. Persistence and projection

Target evidence:

```text
results/runs/<run-id>/
├── resource_samples.jsonl
└── resource_summary.jsonl
```

DuckDB projection should expose:

- per-run/model resource summaries;
- per-capability efficiency summaries;
- execution-signature-aware history;
- explicit UNKNOWN / NON_COMPARABLE states.

## 4. UI

### Model view

Show resource history only within compatible execution lineage:

- latency;
- throughput;
- token usage;
- known API cost;
- peak/average RAM when available;
- CPU when available;
- accelerator memory when reliably reported.

### Run view

Add an expandable resource panel with:

- sampling source;
- sample count;
- peak values;
- timeline where useful;
- missing-metric explanation.

### Compare view

Quality remains primary.

Efficiency comparison is shown only when semantics are compatible. If execution signatures differ, label performance/resource comparison as NON_COMPARABLE while still allowing quality comparison when benchmark signatures match.

## 5. Immutable share renderer

Input is a frozen MCB-11 share snapshot.

Renderer output:

```text
results/shares/<snapshot-id>/
├── snapshot.json
├── card-01.png
├── card-02.png
├── card-03.png
├── card-04.png
├── card-05.png
└── carousel.pdf
```

Suggested five-card story:

1. finding / headline;
2. paired quality comparison;
3. failure-family breakdown;
4. efficiency, only where comparable;
5. methodology + provenance.

Every asset must preserve snapshot ID and benchmark provenance.

## 6. Renderer requirements

Use dedicated fixed-size React share routes/components and a headless browser renderer.

Requirements:

- deterministic viewport and aspect ratio;
- deterministic font/layout inputs;
- no live provider calls;
- no live database joins during rendering;
- snapshot checksum included in rendered provenance;
- PNG output;
- optional multi-page PDF;
- failure if the snapshot schema is unsupported.

## 7. Visual regression

Golden fixtures must cover:

- result card;
- failure breakdown;
- efficiency card with known metrics;
- efficiency card with unavailable metrics;
- methodology card;
- full five-card carousel.

The visual gate should detect layout overflow and material changes, while remaining separate from benchmark-science tests.

## 8. CLI target

```bash
uv run model-bench share render --snapshot <snapshot-id>
```

Optional:

```bash
uv run model-bench share render \
  --snapshot <snapshot-id> \
  --format png,pdf
```

## 9. Definition of Done

- [ ] optional resource telemetry contract is versioned;
- [ ] Korgis/runtime telemetry is captured when exposed;
- [ ] missing telemetry remains explicit and non-fatal;
- [ ] resource summaries are execution-signature aware;
- [ ] Model/Run/Compare surfaces expose comparable efficiency correctly;
- [ ] share snapshots render deterministically to PNG;
- [ ] five-card carousel can be rendered to PDF;
- [ ] public cards include snapshot/methodology provenance;
- [ ] visual regression fixtures cover the share surfaces;
- [ ] Python/frontend/renderer gates pass without provider calls.
