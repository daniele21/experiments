# RedactGuard realistic document benchmark dataset

This dataset keeps **original heterogeneous source files**, **canonical Markdown**, and **PII gold annotations** conceptually separate.

- `canonical/` contains one Markdown file for each source document.
- `annotations/` contains deterministic RedactGuard gold annotations and exact spans.
- `manifest.json` maps every source Drive file to canonical text, annotation file, benchmark profile, and integrity hashes.

## Canonical rule

Canonical Markdown represents what is actually present in the source document, **not** what Docling, OCR, Google Drive text extraction, or an LLM happened to recover.

Structural boundaries are encoded as HTML comments such as `<!-- page: 1 -->`, `<!-- sheet: Clienti -->`, and `<!-- slide: 1 -->`. Model-only benchmark loaders remove those marker lines and preserve every other character exactly. Gold spans are resolved on that transformed inference text.

The scan-heavy PDFs were visually transcribed so OCR mistakes do not become ground truth. Office/tabular formats preserve their visible document structure in Markdown.

## Gold annotations

Annotation contract: `redactguard-gold-v2`, gold version `deterministic_v0.2`.

The 11 documents currently contain **1,566 gold spans** across `account_number`, `private_person`, `private_address`, `private_email`, `private_phone`, and `private_date`. Every annotation stores the expected inference-text SHA-256 to detect drift.

The current gold is deterministic and source-derived, but not independently human-reviewed (`human_reviewed=false`).

### Semantic independence

The 11 source documents map to **6 semantic content families** through `content_family_id`.
Format variants remain separate documents for extraction/end-to-end analysis, but model-capability
reporting must not treat them as 11 independent semantic samples.

In particular, `contratto.doc` and `contratto.docx` have identical inference text and are
explicitly grouped in the same family. The evaluation now reports `macro_family` and
`by_family` alongside document-level and micro metrics.

### Benchmark-only PII subtypes

Gold spans now carry `pii_subtype` for diagnostic analysis without changing the RedactGuard
model output contract. Examples include `iban`, `vat_number`, `fiscal_code`,
`invoice_id`, `customer_record_id`, `invoice_date`, `contact_person`, and
`postal_address`.

Models still return only `pii_type + value`. Subtypes are used to explain where recall/leakage
problems originate.

## Benchmark use

1. **Model-only:** canonical Markdown → strip structure markers → Korgis/model → PII scoring.
2. **Extraction:** original file → parser/OCR → compare with canonical Markdown/gold.
3. **End-to-end:** original file → parser/OCR → Korgis/model → compare with original gold.

Do not derive gold annotations from the model being evaluated.
