# RedactGuard semantic challenge set

This dataset is a **model-capability challenge set**, not an extraction benchmark.

It complements `data/realistic` by testing whether a model applies the RedactGuard
policy contextually rather than merely recognizing obvious patterns.

## Design

- 45 compact cases across General, Healthcare, Financial, and Legal.
- Positive, negative, and contrast-pair cases.
- Hard negatives reuse values or surface forms that would be protected in another context.
- Every case carries a `content_family_id` so contrast variants can be analyzed together.
- Gold entities may include a benchmark-only `pii_subtype`; models are still scored on the
  unchanged RedactGuard `pii_type + value` output contract.
- `human_reviewed=false` until independent review/adjudication is completed.

## Why this exists

The realistic document set is valuable for document-scale behavior and heterogeneous formats,
but it contains repeated semantic content and a heavy concentration of easy tabular PII.
This challenge set is deliberately small and diagnostic.

Examples of contrast pairs:

- personal address vs standalone city/location;
- personal event date vs product release date;
- protected financial VAT/IBAN/invoice ID vs public/demo/product-code use;
- patient diagnosis/treatment/lab value vs generic clinical documentation;
- protected legal record contact/date/URL vs public legal information.

## Running

```bash
uv run redact-bench check-data --dataset data/challenge/cases.jsonl

uv run redact-bench compare \
  --dataset data/challenge/cases.jsonl
```

For a managed four-model run:

```bash
uv run redact-bench suite --config config/suite-challenge.yaml
```

## Review status

Current version: `challenge_v0.1`.

The cases are deterministic and hand-authored but are **not yet independently human-reviewed**.
Do not present them as adjudicated gold until the review fields are updated after review.
