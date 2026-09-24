# Realistic test dataset

The **model-only realistic dataset is committed in this repository** so a fresh clone can validate and run it without downloading anything from Google Drive.

The original heterogeneous source documents remain external because they are only required for extraction/OCR/full end-to-end tests.

## Dataset locations

Committed benchmark dataset:

```text
data/realistic/
├── README.md
├── manifest.json
├── canonical/
│   └── <source filename>.md
└── annotations/
    ├── README.md
    ├── summary.json
    └── <source filename>.json
```

Upstream prepared dataset in Google Drive:

- https://drive.google.com/drive/folders/1W_fxTf1nLNBfzD5LVQtdLCLcBxrhP4c2

Original heterogeneous source documents:

- https://drive.google.com/drive/folders/1IB49Z2f5tYcgB41p-gaFUGOeFcv29tPK

The Drive prepared dataset remains the upstream source used when intentionally revising canonical text or gold annotations. The committed copy is the reproducible version used by this experiment.

## Dataset contract

Current dataset id:

```text
redactguard-realistic-documents-v0.1
```

The set contains 11 heterogeneous source documents represented as canonical Markdown and deterministic gold annotations.

Canonical Markdown represents the **visible/source content**, not parser/OCR output. Structural markers such as:

```html
<!-- page: 1 -->
<!-- sheet: Clienti -->
<!-- slide: 2 -->
<!-- embedded-image: 1 -->
```

are metadata. The benchmark strips the complete marker line before model inference and preserves every other character.

Gold spans are defined against the exact stripped inference text, not against the raw Markdown file.

Each annotation JSON records:

- RedactGuard profile;
- exact character spans;
- PII type and value;
- inference-text character count;
- SHA-256 of the exact inference text;
- labeling policy and provenance.

The dataset is deterministic gold, not independently human-reviewed gold.

## Model-only usage

After cloning or pulling current `main`, no dataset download step is required.

Validate the committed dataset:

```bash
uv run redact-bench check-realistic-dataset \
  --dataset-dir data/realistic
```

Then run all configured local models:

```bash
uv run redact-bench compare \
  --dataset data/realistic
```

Or a subset:

```bash
uv run redact-bench compare \
  --dataset data/realistic \
  --models nemotron-nano-4b,qwen3.5-4b-q4km
```

No intermediate JSONL export is required.

The loader performs:

```text
manifest.json
      ↓
canonical/<document>.md
      ↓
strip structural marker lines
      ↓
verify text length + SHA-256
      ↓
annotations/<document>.json
      ↓
verify every exact gold span
      ↓
Case(profile, inference_text, gold)
      ↓
normal RedactGuard benchmark runner
```

The source filename becomes the benchmark `case_id`, so results remain traceable to the original document format.

## Original files for extraction/E2E work

Only extraction/OCR/full heterogeneous tests need the original binaries.

Download the original Drive folder and place the files under:

```text
data/realistic/originals/
├── scansione_nuda.pdf
├── scansione_cercabile.pdf
├── scansione_con_immagini.pdf
├── contratto.pdf
├── contratto.doc
├── contratto.docx
├── tabella_piccola.xlsx
├── cartella_multifoglio.xlsx
├── clienti.csv
├── lettera.txt
└── presentazione.pptx
```

`data/realistic/originals/` is ignored by Git.

Check completeness with:

```bash
uv run redact-bench check-realistic-dataset \
  --dataset-dir data/realistic \
  --require-originals
```

The existing `redact-bench documents` command is currently a PDF/Docling system tier. The realistic originals include DOC, DOCX, XLSX, CSV, TXT and PPTX as well, so the heterogeneous end-to-end tier must preserve format-specific extraction behavior rather than forcing every format through the PDF-only runner.

## Latency on selected realistic documents

The generic latency command also accepts the dataset directory. Explicitly select realistic source filenames because the default latency ids belong to the smoke set:

```bash
uv run redact-bench latency \
  --dataset data/realistic \
  --case-ids lettera.txt,presentazione.pptx,contratto.pdf \
  --warmups 5 \
  --repeats 30
```

## Updating the dataset

Never edit canonical Markdown locally just to improve a model score.

When the realistic dataset intentionally changes:

1. update the prepared Drive dataset;
2. update annotation spans/hashes;
3. copy the new canonical/annotation/manifest version into `data/realistic/`;
4. run `check-realistic-dataset`;
5. update the dataset id/version when the benchmark contract changes;
6. merge only after CI validates the committed dataset.

A hash mismatch is a dataset-version failure, not something the benchmark should silently repair.
