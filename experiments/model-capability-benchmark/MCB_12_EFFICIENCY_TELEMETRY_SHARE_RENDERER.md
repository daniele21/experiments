# MCB-12 — Efficiency Telemetry & Share Renderer

Status: **CORE COMPLETE — REAL CHROME RENDER GATE PASSING**

Depends on:

- MCB-10 vertical benchmark hardening;
- MCB-11 observability/results explorer core.

Implemented in the MCB-12 core slice:

- Korgis `/api/v1/resources` now exposes source-labelled host/runtime observations without PIDs or private paths;
- MCB samples resource evidence during local Korgis inference with bounded telemetry timeout and explicit opt-out;
- telemetry failures are non-fatal and unavailable metrics remain null;
- raw resource samples and summaries are persisted separately from quality evidence;
- DuckDB projects CURRENT resource summaries by execution lineage;
- execution signatures include privacy-safe hardware identity (OS/arch/CPU/total memory);
- Model, Run and Compare surfaces expose CPU/RSS evidence with NON_COMPARABLE guardrails;
- immutable share snapshots render to five 1080×1350 PNG cards and a PDF carousel;
- the renderer performs no live provider calls or analytics joins;
- CI runs Python/frontend gates and a real Chrome headless render, validates PNG dimensions/PDF output and uploads the rendered cards for visual review.

The current visual gate is structural/deterministic rather than a brittle pixel-by-pixel hash. A stricter perceptual/pixel-diff baseline can be added later without changing the snapshot or renderer contracts.

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

Use dedicated fixed-size snapshot-only HTML card templates and a headless Chrome renderer.

Requirements:

- deterministic viewport and aspect ratio;
- deterministic font/layout inputs;
- no live provider calls;
- no live database joins during rendering;
- content-addressed snapshot ID included in rendered provenance;
- PNG output;
- optional multi-page PDF;
- failure if the snapshot schema is unsupported.

## 7. Visual validation

The committed snapshot fixture and renderer tests cover:

- result card;
- paired-quality card;
- failure-family breakdown;
- efficiency card with comparable evidence;
- efficiency card with unavailable/non-comparable evidence;
- methodology/provenance card;
- full five-card carousel contract.

CI additionally performs a real Chrome render and verifies:

- five PNG files are produced;
- every PNG is exactly 1080 × 1350;
- a PDF carousel is produced;
- rendered artifacts are uploaded for human visual inspection.

A future perceptual/pixel-diff baseline may tighten regression detection, but it is deliberately separate from benchmark-science tests and is not required for the renderer contract.

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

- [x] optional resource telemetry contract is versioned;
- [x] Korgis/runtime telemetry is captured when exposed;
- [x] missing telemetry remains explicit and non-fatal;
- [x] resource summaries are execution-signature and hardware-lineage aware;
- [x] Model/Run/Compare surfaces expose comparable efficiency correctly;
- [x] share snapshots render deterministically to PNG;
- [x] five-card carousel can be rendered to PDF;
- [x] public cards include content-addressed snapshot/methodology provenance;
- [x] structural visual fixtures cover the share surfaces;
- [x] Python/frontend/real-Chrome renderer gates pass without provider calls.
