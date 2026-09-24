# PII gold annotations

`annotations/` contains one JSON file for every canonical document. The files implement the frozen RedactGuard gold contract used by the realistic-document benchmark.

## Span contract

Gold spans are calculated on the exact text sent to the model-only benchmark:

1. start from the matching `canonical/*.md` file;
2. remove complete structural-marker lines such as `<!-- page: 1 -->`, `<!-- sheet: Clienti -->`, `<!-- slide: 2 -->`, and `<!-- embedded-image: 1 -->`;
3. preserve every other character and whitespace exactly;
4. resolve all `[start, end)` offsets on that transformed text.

Each annotation stores `inference_text_sha256` and `inference_text_chars`, so a loader can fail fast if canonical text or transform logic drifts.

## Annotation schema

Each file contains:

- `profile`: RedactGuard profile to use for inference (`legal` or `financial`);
- `entities`: grouped `(pii_type, value)` records with occurrence counts;
- `spans`: exact `[start, end)` gold spans plus source rule and page/sheet/slide attribution when available;
- `summary.by_type`: counts by PII type;
- `gold_policy`: explicit inclusion/exclusion decisions.

## Gold policy v0.1

Included: person names, emails, phone numbers, postal addresses or locations structurally tied to a person/account record, explicit financial-event dates, fiscal codes, VAT numbers, IBANs, customer IDs and invoice IDs when they identify a record.

Excluded: organization names and monetary amounts because the frozen RedactGuard taxonomy used by this benchmark has no dedicated PII type for them. A standalone place is not annotated merely because the same city appears elsewhere as an address.

## Review status

These annotations are **deterministic gold v0.1**, generated from the canonical source and structural column semantics and validated for exact substring/hash consistency. `human_reviewed` is intentionally `false`: do not describe this version as independently human-reviewed.

The benchmark should treat any canonical hash mismatch as an invalid dataset state rather than silently recomputing spans.
