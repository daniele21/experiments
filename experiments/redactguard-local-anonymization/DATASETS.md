# Datasets

## Smoke text v0.1

`data/smoke/cases.jsonl` contains 20 deterministic Italian text cases across:

- General;
- Healthcare;
- Financial;
- Legal.

It includes positive, negative, repeated-value and dense-PII examples. Gold spans are deterministically resolved from committed `value` annotations, which keeps the file human-readable.

This dataset is intentionally too small for model-quality claims.

## Document E2E smoke v0.2

`data/documents/manifest.jsonl` contains five deterministic synthetic documents / six pages across the same four RedactGuard profiles. It includes:

- contact and identity PII;
- multi-page healthcare content;
- financial identifiers;
- legal content;
- a repeated-value case.

The manifest stores canonical page text and gold entities. PDF files are generated on demand with:

```bash
uv sync --extra dev --extra documents
uv run redact-bench make-document-fixtures
```

Generated PDFs live under `data/documents/generated/` and are ignored by Git. This keeps the source of truth reviewable and avoids opaque binary fixtures.

The end-to-end runner processes those PDFs through Docling before any model inference. Gold entities that cannot be aligned to extracted text are recorded as extraction misses and count against end-to-end privacy quality.

### Real/private documents

The same runner can evaluate external PDFs. Create a compatible manifest whose `filename` values match files in a separate fixture directory, then run:

```bash
uv run redact-bench documents \
  --manifest /path/to/private-manifest.jsonl \
  --fixtures-dir /path/to/private-pdfs \
  --no-generate-fixtures
```

Do not commit private documents, extracted text or result artifacts containing sensitive information.

## Next quality tier

Use two complementary sources.

### Generic PII

Adopt an externally labelled Italian PII dataset with character spans and an explicit taxonomy mapping. Dataset-native labels that do not map to the RedactGuard policy must be marked `excluded_from_scoring`, never silently converted to negatives.

### RedactGuard domain set

Create a deterministic/domain-reviewed dataset for RedactGuard-specific categories that generic PII corpora often omit:

- `health_condition`;
- `health_treatment`;
- `health_lab_result`;
- `personal_measurement`;
- `lifestyle_info`;
- organization-specific custom PII.

Ground truth must come from deterministic generation or independent human review, never from the same model being evaluated.

### Document-layout tier

Extend the PDF corpus with independently reviewed layouts such as:

- multi-column documents;
- tables;
- scanned/OCR PDFs;
- headers/footers;
- forms;
- long multi-page reports.

Extraction and model metrics must remain separate.

## Split policy

Model/prompt selection must use development/validation data only. A final benchmark split must remain untouched until the benchmark protocol is frozen.

## Public-data policy

Do not commit upstream dataset bytes unless the license and redistribution policy explicitly support it. Cache downloaded datasets under `data/cache/`.

Generated synthetic PDFs are reproducible artifacts and should not be committed. Private document bytes and extracted outputs must remain outside the repository.
