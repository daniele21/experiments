# RedactGuard local anonymization benchmark

Reproducible benchmark for measuring how local models perform as the **PII detection engine of RedactGuard** when served by **Korgis**, both on frozen text inputs and through the full **PDF → Docling → Korgis → RedactGuard post-processing** path.

The benchmark never embeds an inference engine. Korgis remains a separate repository/runtime reached through its public HTTP/control-plane contracts. The managed suite can launch and stop that external Korgis process for reproducible benchmark runs.

## What this experiment answers

> Which local model / quantization gives RedactGuard the best privacy-quality-latency trade-off?

Evaluation v3 keeps **model quality** and **system effectiveness** separate.

Quality metrics are computed only when the transport, structured-output contract and
application parser all succeed:

- PII recall;
- character leakage rate;
- zero-leak document rate;
- precision and over-redaction;
- p50 / p95 / p99 client-observed inference latency.

System metrics additionally expose the privacy consequence of inference failures:

- inference success / contract-valid rate;
- truncation rate;
- span-resolution rate;
- system recall;
- system leakage.

An invalid or truncated inference is therefore never displayed as artificial
`0% recall / 100% precision`. Quality is `N/A`; system risk remains visible.

The primary scoring unit is the **final RedactGuard span set after deterministic post-processing**, not merely the model's raw JSON.

## Compatibility baseline

This v0.1 is pinned to:

- RedactGuard detection-v2 contract snapshot: `daniele21/redact-guard@ab8855a3d644c479b00a4dc3e5d7b5f949f4f5b1`;
- detection contract id: `redactguard-detection-v2`;
- model-facing schema: minimal `pii_type + value`;
- default inference budgets: 4,096 output tokens, 4,000 input characters per segment, 256-character overlap;
- Korgis recent development baseline: `daniele21/korgis@eadd5dca94417dd037a5d43650377b349875ab17` (`dev`);
- Korgis identity protocol: `local-llm-identity-v1`;
- inference API: `POST /v1/chat/completions`;
- lifecycle API: `/api/v1/models/activate`;
- reproducibility evidence: `GET /v1/runtime/identity`.

Korgis `dev` is deliberate here: that revision contains the recent Qwen3.5 Q4_K_M registry additions used by this benchmark. Do not silently run an older Korgis checkout and publish the results as comparable evidence.

## Initial local model matrix

All four keys are present in the pinned Korgis registry:

| Key | Model | Quantization | Purpose |
|---|---|---|---|
| `nemotron-nano-4b` | NVIDIA Nemotron-3-Nano-4B | Q4_K_M | RedactGuard-size baseline |
| `nemotron-nano-4b-q8` | NVIDIA Nemotron-3-Nano-4B | Q8_0 | quantization comparison |
| `qwen3.5-4b-q4km` | Qwen3.5-4B | Q4_K_M | same-size model comparison |
| `qwen3.5-9b-q4km` | Qwen3.5-9B | Q4_K_M | larger-local reference |

## Managed benchmark suite

For normal use, **do not start `local-llm` from this experiment environment**. The `local-llm` executable belongs to the Korgis project, which has its own Python environment.

One-time prerequisites:

1. clone/update Korgis somewhere on the same machine;
2. install `llama-server` when using the GGUF llama.cpp backend;
3. install this experiment with `uv sync --extra dev`.

A convenient local layout is:

```text
~/Personal/
├── experiments/
└── korgis/
```

The suite auto-discovers sibling repositories named `korgis` or `local-llm-server`. If yours lives elsewhere, pass `--korgis-repo` or set `KORGIS_REPO`.

From this experiment directory, the normal workflow is one command:

```bash
uv run redact-bench suite
```

Or explicitly:

```bash
uv run redact-bench suite --korgis-repo ~/Personal/korgis
```

The suite configuration lives in [`config/suite.yaml`](config/suite.yaml). It defines the dataset, model matrix, dedicated Korgis endpoint and latency protocol.

The managed suite performs:

```text
validate realistic dataset
        ↓
resolve Korgis repository
        ↓
ensure configured model artifacts
        ↓
for each model
    start a fresh Korgis process on :12435
    run quality benchmark
    run repeated latency benchmark
    stop Korgis completely
        ↓
combine per-model evidence
        ↓
append results/history.jsonl
        ↓
rebuild results/dashboard.html
```

Each model gets a fresh Korgis process. This is deliberate: current Korgis `/activate` loads/selects another runtime but does not imply that previously resident runtimes have been unloaded. Restart-per-model prevents resident-model accumulation from contaminating memory state or model comparisons.

To test only a subset:

```bash
uv run redact-bench suite \
  --models nemotron-nano-4b,qwen3.5-4b-q4km
```

The default suite ensures model artifacts through Korgis. To require already-downloaded models instead:

```bash
uv run redact-bench suite --no-ensure-models
```

After a completed suite:

```bash
open results/dashboard.html
```

The dashboard is static and local. It shows the latest comparison, PII-type breakdown and an append-only history of previous suites with links to detailed quality and latency reports.


### Interactive React dashboard

For day-to-day exploration, the recommended UI is the React dashboard under
[`ui/`](ui/). Unlike the legacy generated `results/dashboard.html`, it does not depend
on `history.jsonl` and also discovers ordinary `compare` runs such as
`results/<run-id>/`.

Install the frontend dependencies once:

```bash
npm --prefix ui install
```

Then launch it from the experiment root:

```bash
uv run redact-bench ui
```

Open `http://127.0.0.1:5173`.

The UI reads `results/` dynamically through the local Vite server and refreshes the run
index every five seconds. No export/rebuild step is required. It supports direct benchmark
runs plus managed suite layouts under either `results/suite/` or `results/suites/`.

The dashboard includes:

- **Client Output Preview** as the default view: a product/client-facing PII recognition summary driven by the actual findings of the selected model/document, with masked values, category footprint and suggested redactions;
- a separate **benchmark-only validation panel** below the client preview showing the hidden gold truth (recall, leakage, precision, missed spans), specifically to catch cases where a polished client output looks complete while the benchmark knows PII was missed;
- run selector with automatic discovery of newly completed runs;
- recall, leakage, precision, zero-leak and latency KPI cards;
- recall-vs-latency trade-off chart across models;
- per-PII-type recall / precision / leakage chart;
- all-model comparison table;
- model-specific failure explorer;
- benchmark, Korgis and host provenance;
- unified cross-run overview that places all models in one comparison, using the newest complete evidence per model and falling back to clearly labelled partial evidence when needed.


A suite writes:

```text
results/
├── history.jsonl
├── dashboard.html
└── suites/
    └── <suite-id>/
        ├── suite.json
        ├── logs/
        │   ├── nemotron-nano-4b.log
        │   └── ...
        ├── quality/
        │   ├── manifest.json
        │   ├── metrics.json
        │   ├── failures.json
        │   ├── <model>.jsonl
        │   └── report.html
        └── latency/
            ├── manifest.json
            ├── metrics.json
            ├── <model>.jsonl
            └── report.html
```

`history.jsonl` is append-only: repeated suites never overwrite prior measurements. `suite.json` records lifecycle status and preserves a failure reason when a suite aborts.

### Manual/advanced operation

The lower-level `compare`, `latency` and `documents` commands still expect an already-running external Korgis server. They are useful for debugging, but the managed `suite` command is the recommended path for repeatable model comparison.

If you intentionally operate Korgis yourself:

```bash
cd /path/to/korgis
uv run --frozen local-llm serve \
  --model nemotron-nano-4b \
  --enable-admin-api \
  --no-download
```

Then, from this experiment:

```bash
uv run redact-bench check-korgis
uv run redact-bench preflight
```

`preflight` activates each selected model and verifies that the Korgis/backend path can
produce a valid RedactGuard v2 structured response before any dataset quality score is
accepted. `compare` and `latency` run the same gate automatically unless explicitly
disabled for diagnostics with `--no-preflight`.

## Realistic test dataset

The realistic model-only dataset is committed under `data/realistic/`: 11 heterogeneous source representations, canonical Markdown and exact deterministic PII gold spans. A fresh clone does not need a Drive download for model comparison.

Usage and the separate original-document/E2E flow are documented in [REALISTIC_DATASET.md](REALISTIC_DATASET.md).

```bash
uv run redact-bench check-realistic-dataset --dataset-dir data/realistic
uv run redact-bench compare --dataset data/realistic
```

`compare` shows live progress on an interactive terminal, including model/warmup status,
completed cases, percentage, last case, last inference latency, elapsed time, ETA and
provider errors. Progress is written to stderr so stdout remains the final run path for
scripts and shell composition.

Example:

```text
Run: 20260928T...
Dataset: realistic — 11 cases
Models: 4
Results: results/20260928T...

[1/4 nemotron-nano-4b] Cases 4/11 [███████░░░░░░░░░░░░░] 36% | Last: contratto.pdf | Latency: 2.8s | Elapsed: 00:48 | ETA: 01:24 | Errors: 0
```

For CI or intentionally quiet runs:

```bash
uv run redact-bench compare --dataset data/realistic --no-progress
```

`compare --dataset` accepts either the committed JSONL smoke dataset or the committed
realistic dataset directory. The loader strips structural metadata markers, verifies the
frozen SHA-256 and loads the exact annotated spans; no intermediate JSONL conversion is
required.

The `compare` command is explicitly a **model-capability** benchmark over canonical
document text. Long inputs are split with the same deterministic segmentation contract
used by RedactGuard v2, then findings are mapped back to global document offsets and
de-duplicated. The separate `documents` benchmark is the **RedactGuard-fidelity E2E**
path: PDF → Docling page → bounded RedactGuard inference segments → merged page result.

Only `data/realistic/originals/` is ignored by Git; download those original binaries from Drive only for extraction/end-to-end work.

## Document end-to-end benchmark

The repository also implements a separate system-level benchmark that starts from PDFs. It deliberately keeps extraction evidence separate from model evidence:

```text
canonical source + gold PII
        ↓
synthetic PDF fixture
        ↓
Docling (same page-export contract as RedactGuard)
        ↓
extraction alignment / extraction recall
        ↓
Korgis
        ↓
local model
        ↓
RedactGuard-compatible value → span resolution
        ↓
model metrics on extracted text
        +
end-to-end privacy metrics
```

Install the document-only dependencies:

```bash
uv sync --extra dev --extra documents
```

Validate the committed document manifest and optionally generate the PDFs without running inference:

```bash
uv run redact-bench check-documents
uv run redact-bench make-document-fixtures
```

Run all configured local models end to end:

```bash
uv run redact-bench documents
```

Or a subset:

```bash
uv run redact-bench documents \
  --models nemotron-nano-4b,qwen3.5-4b-q4km
```

The generated PDFs are intentionally ignored by Git. Their canonical source text and gold annotations live in `data/documents/manifest.jsonl`, so the fixtures can be regenerated deterministically.

For real/private PDFs, place files with matching manifest filenames in a separate fixture directory and run with `--no-generate-fixtures --fixtures-dir <path>`. Do not commit private document bytes.

The document run writes the normal manifest/report plus `extraction.json`. The report exposes three distinct layers:

1. **Extraction quality** — whether Docling preserved the gold PII and source text.
2. **Model quality on extracted text** — what the LLM did given the text it actually received.
3. **End-to-end privacy quality** — PII lost during extraction counts as a miss/leak, so parser failures cannot disappear from the final system score.

## Evaluation v3

Evaluation v3 fixes the central ambiguity in the original benchmark.

For each case, evidence is tracked through:

```text
transport
  -> structured output / termination
  -> JSON + schema validation
  -> value-to-source span resolution
  -> model-quality scoring
  -> system-effectiveness scoring
```

**Model quality** is available only for valid inference cases. **System effectiveness**
treats failed inference conservatively as unprotected source PII while preserving the
failure cause.

The result artifacts expose:

- micro and macro model-quality metrics;
- system recall and system leakage;
- inference-success and evaluated-case coverage;
- contract-valid and truncation rates;
- raw → resolved model-item counts and span-resolution rate;
- by-type and by-document metrics;
- typed failure analysis;
- per-model preflight evidence;
- RedactGuard contract version + source revision;
- effective per-model inference budgets.

Historical v2 results remain discoverable in the React dashboard but are labelled
`LEGACY` / diagnostic-only. Current v3 evidence is preferred automatically in the
unified model overview.


## Run the comparison

```bash
uv run redact-bench compare
```

For benchmark-grade repeated latency evidence:

```bash
uv run redact-bench latency --warmups 5 --repeats 30
```

Or select a smaller matrix:

```bash
uv run redact-bench compare   --models nemotron-nano-4b,qwen3.5-4b-q4km
```

Each run creates:

```text
results/<run-id>/
├── manifest.json
├── metrics.json
├── failures.json
├── rows.json
├── <model>.jsonl
└── report.html
```

The manifest captures the exact Korgis runtime identity for every activated model. `metrics.json` uses `redactguard-evaluation-v3` and contains quality, system,
micro/macro, by-type, by-profile and by-document views. `preflight.json` records the
model/runtime contract gate. `failures.json` separates inference-contract failures from
false negatives/false positives produced by valid inference.

## What is copied from RedactGuard

The experiment freezes only the behavior needed to make results reproducible:

1. built-in PII profile taxonomy, descriptions and examples;
2. RedactGuard detection-contract version and provenance;
3. compact system-prompt/output contract;
4. bounded segmentation settings;
5. value-to-source-span post-processing semantics.

It does **not** depend on the RedactGuard Python package at runtime and does not import Korgis code. This keeps both product repositories independently evolvable while making benchmark drift explicit.

## Current dataset scope

`data/smoke/cases.jsonl` is a small deterministic text integration dataset spanning General, Healthcare, Financial and Legal profiles. `data/documents/manifest.jsonl` adds five deterministic synthetic document cases (six pages) for the PDF/Docling system tier. Both are harness-validation datasets, not sufficient for publishing broad model-quality conclusions.

The realistic heterogeneous model-only dataset is committed as a reproducible test tier; the original heterogeneous binaries remain access-controlled on Drive. A future publication-grade tier should still add independently reviewed/external labels and a held-out split. See [DATASETS.md](DATASETS.md) and [REALISTIC_DATASET.md](REALISTIC_DATASET.md).

## Boundary with the RedactGuard product

RedactGuard `main` now uses Korgis as the external local runtime boundary and no longer owns an embedded `llama_cpp_server.py`, GGUF downloader, or private model lifecycle. The product integration baseline is `b5ac4377b2947ccb954369c3df7cce1e13994df8`.

The benchmark pins an explicit RedactGuard v2 contract snapshot in
`config/profiles.yaml`. Updating product detection behavior requires an intentional
snapshot refresh and a new benchmark run; historical evidence is never silently
reinterpreted under a newer contract.
