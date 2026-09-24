# RedactGuard local anonymization benchmark

Reproducible benchmark for measuring how local models perform as the **PII detection engine of RedactGuard** when served by **Korgis**, both on frozen text inputs and through the full **PDF → Docling → Korgis → RedactGuard post-processing** path.

The benchmark does not embed Korgis and does not start a private inference engine. Korgis is an external local service reached only through its current public HTTP/control-plane contracts.

## What this experiment answers

> Which local model / quantization gives RedactGuard the best privacy-quality-latency trade-off?

Primary metrics are intentionally privacy-oriented:

- PII recall;
- character leakage rate;
- zero-leak document rate;
- precision and over-redaction;
- valid JSON rate;
- p50 / p95 / p99 client-observed inference latency.

The primary scoring unit is the **final RedactGuard span set after deterministic post-processing**, not merely the model's raw JSON.

## Compatibility baseline

This v0.1 is pinned to:

- frozen RedactGuard detection contract source: `daniele21/redact-guard@70ea5ed4fbbd7182010cc04eb756f636791c5947`;
- current RedactGuard Korgis integration baseline: `daniele21/redact-guard@b5ac4377b2947ccb954369c3df7cce1e13994df8` (`main`);
- Korgis recent development baseline: `daniele21/korgis@26a161dc0ef89a133c7a076d3a31544a274c1469` (`dev`);
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

## Setup

Clone Korgis next to this repository and check out the tested revision:

```bash
git clone https://github.com/daniele21/korgis.git
cd korgis
git checkout 26a161dc0ef89a133c7a076d3a31544a274c1469

python3 -m pip install "uv==0.8.13"
uv sync --frozen --extra dev
```

Install `llama-server` if it is not already available:

```bash
brew install llama.cpp
command -v llama-server
```

Download the model artifacts through **Korgis itself**:

```bash
uv run --frozen local-llm download nemotron-nano-4b
uv run --frozen local-llm download nemotron-nano-4b-q8
uv run --frozen local-llm download qwen3.5-4b-q4km
uv run --frozen local-llm download qwen3.5-9b-q4km
```

Start only an anchor model; the benchmark activates the requested models sequentially:

```bash
uv run --frozen local-llm serve   --model nemotron-nano-4b   --enable-admin-api   --no-download
```

In a second terminal:

```bash
cd experiments/redactguard-local-anonymization
uv sync --extra dev
uv run redact-bench check-korgis
uv run redact-bench check-data
```

## Realistic test dataset

The realistic model-only dataset is committed under `data/realistic/`: 11 heterogeneous source representations, canonical Markdown and exact deterministic PII gold spans. A fresh clone does not need a Drive download for model comparison.

Usage and the separate original-document/E2E flow are documented in [REALISTIC_DATASET.md](REALISTIC_DATASET.md).

```bash
uv run redact-bench check-realistic-dataset --dataset-dir data/realistic
uv run redact-bench compare --dataset data/realistic
```

`compare --dataset` accepts either the committed JSONL smoke dataset or the committed realistic dataset directory. The loader strips structural metadata markers, verifies the frozen SHA-256 and loads the exact annotated spans; no intermediate JSONL conversion is required.

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
├── rows.json
├── <model>.jsonl
└── report.html
```

The manifest captures the exact Korgis runtime identity for every activated model.

## What is copied from RedactGuard

The experiment freezes only the behavior needed to make results reproducible:

1. built-in PII profile taxonomy, descriptions and examples;
2. RedactGuard system-prompt contract;
3. value-to-source-span post-processing semantics.

It does **not** depend on the RedactGuard Python package at runtime and does not import Korgis code. This keeps both product repositories independently evolvable while making benchmark drift explicit.

## Current dataset scope

`data/smoke/cases.jsonl` is a small deterministic text integration dataset spanning General, Healthcare, Financial and Legal profiles. `data/documents/manifest.jsonl` adds five deterministic synthetic document cases (six pages) for the PDF/Docling system tier. Both are harness-validation datasets, not sufficient for publishing broad model-quality conclusions.

The realistic heterogeneous model-only dataset is committed as a reproducible test tier; the original heterogeneous binaries remain access-controlled on Drive. A future publication-grade tier should still add independently reviewed/external labels and a held-out split. See [DATASETS.md](DATASETS.md) and [REALISTIC_DATASET.md](REALISTIC_DATASET.md).

## Boundary with the RedactGuard product

RedactGuard `main` now uses Korgis as the external local runtime boundary and no longer owns an embedded `llama_cpp_server.py`, GGUF downloader, or private model lifecycle. The product integration baseline is `b5ac4377b2947ccb954369c3df7cce1e13994df8`.

The benchmark deliberately keeps the earlier RedactGuard detection-contract SHA frozen because the migration changed runtime plumbing, not the benchmarked prompt/taxonomy/value-to-span semantics. This preserves reproducibility while keeping the product and experiment on the same Korgis architecture.
