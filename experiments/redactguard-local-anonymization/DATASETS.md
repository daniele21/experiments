# Datasets

## Smoke v0.1

`data/smoke/cases.jsonl` contains 20 deterministic Italian cases across:

- General;
- Healthcare;
- Financial;
- Legal.

It includes positive, negative, repeated-value and dense-PII examples. Gold spans are deterministically resolved from committed `value` annotations, which keeps the file human-readable.

This dataset is intentionally too small for model-quality claims.

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

## Split policy

Model/prompt selection must use development/validation data only. A final benchmark split must remain untouched until the benchmark protocol is frozen.

## Public-data policy

Do not commit upstream dataset bytes unless the license and redistribution policy explicitly support it. Cache downloaded datasets under `data/cache/`, which the repository root already ignores.
