# Realistic test dataset

This experiment has a private, access-controlled realistic dataset for RedactGuard model evaluation.

## Source locations

Prepared benchmark dataset (canonical Markdown + gold annotations + manifest):

- https://drive.google.com/drive/folders/1W_fxTf1nLNBfzD5LVQtdLCLcBxrhP4c2

Original heterogeneous source documents:

- https://drive.google.com/drive/folders/1IB49Z2f5tYcgB41p-gaFUGOeFcv29tPK

The prepared dataset is the source to use for **model-only** comparisons. The original source folder is needed only when testing extraction / OCR / full product behavior.

These folders may require the corresponding Google Drive access. The repository intentionally does not embed Google credentials, Drive API tokens or copies of the private dataset.

## Dataset contract

Current dataset id:

```text
redactguard-realistic-documents-v0.1
```

The prepared Drive folder contains:

```text
README.md
manifest.json
canonical/
  <source filename>.md
annotations/
  README.md
  summary.json
  <source filename>.json
```

The current set contains 11 heterogeneous source documents represented as canonical Markdown and deterministic gold annotations.

Canonical Markdown represents the **visible/source content**, not parser/OCR output. Structural markers such as:

```html
<!-- page: 1 -->
<!-- sheet: Clienti -->
<!-- slide: 2 -->
<!-- embedded-image: 1 -->
```

are metadata. The benchmark strips the complete marker line before model inference and preserves every other character.

Gold spans are therefore defined against the exact stripped inference text, not against the raw Markdown file.

Each annotation JSON records:

- RedactGuard profile;
- exact character spans;
- PII type and value;
- inference-text character count;
- SHA-256 of the exact inference text;
- labeling policy and provenance.

The dataset is currently deterministic gold, not independently human-reviewed gold. Do not describe it as human-reviewed unless that status is changed in the source dataset.

## Get the dataset

### Model-only benchmark

In Google Drive, download the complete **prepared benchmark dataset** folder.

Place its contents here:

```text
experiments/redactguard-local-anonymization/data/realistic/
├── README.md
├── manifest.json
├── canonical/
└── annotations/
```

The final path from this experiment directory must therefore contain:

```bash
test -f data/realistic/manifest.json
test -d data/realistic/canonical
test -d data/realistic/annotations
```

Do not commit this directory. It is intentionally ignored by Git.

Validate the downloaded copy before any benchmark:

```bash
uv run redact-bench check-realistic-dataset \
  --dataset-dir data/realistic
```

Validation fails if any of the following drift:

- expected files;
- canonical → inference-text transformation;
- inference-text length;
- SHA-256;
- RedactGuard profile;
- gold span count;
- span bounds;
- `text[start:end] == gold.value`.

### Original files for extraction/E2E work

If extraction or full heterogeneous end-to-end tests are needed, also download the **original source documents** folder.

Place the files under:

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

Then require source-file completeness during validation:

```bash
uv run redact-bench check-realistic-dataset \
  --dataset-dir data/realistic \
  --require-originals
```

The existing `redact-bench documents` command is currently a PDF/Docling system tier. The realistic heterogeneous originals include DOC, DOCX, XLSX, CSV, TXT and PPTX as well, so they should not be forced through that PDF-only command. Their extraction/E2E integration must preserve format-specific behavior.

## Run model-only comparison

Once validation succeeds, the same `compare` command can read the realistic dataset directory directly:

```bash
uv run redact-bench compare \
  --dataset data/realistic
```

Subset of models:

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
verify SHA-256
      ↓
annotations/<document>.json
      ↓
exact gold spans
      ↓
Case(profile, inference_text, gold)
      ↓
normal RedactGuard benchmark runner
```

The source filename becomes the benchmark `case_id`, so model results remain traceable to the original document.

## Latency on selected realistic documents

The generic latency command also accepts the dataset directory. Because the default latency case ids belong to the smoke set, explicitly select realistic source filenames:

```bash
uv run redact-bench latency \
  --dataset data/realistic \
  --case-ids lettera.txt,presentazione.pptx,contratto.pdf \
  --warmups 5 \
  --repeats 30
```

## Reproducibility rule

Never edit the local canonical Markdown to make a model perform better.

The Drive dataset is the dataset source of truth. If canonical text or gold annotations need to change:

1. change the prepared Drive dataset;
2. update its annotation spans/hashes;
3. download the new version;
4. run `check-realistic-dataset`;
5. record the dataset id/version in benchmark evidence.

A hash mismatch is a dataset-version failure, not something the benchmark should silently repair.
