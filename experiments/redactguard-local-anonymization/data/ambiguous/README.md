# Contextual & Ambiguous PII — synthetic diagnostic challenge

Ambiguous PII: 24 contrast pairs, balanced across general, healthcare, financial and legal contexts.

- 48 **synthetic** text cases, organized as 24 positive/negative contrast pairs, one semantic family per pair.
- Positive: the information belongs to a person or protected record under the pinned `config/profiles.yaml` policy. Negative: similar surface text is generic, illustrative, or public, with no protected record. The negative/positive distinction is contextual, **not a legal determination**.
- Explicit `pii_subtype` is diagnostic metadata, **not a new model-facing PII type**.
- All labels `human_reviewed: false`. Synthetic examples need independent policy and clinical/legal review before publication as gold-standard scores.
- **This is capability probing on text**, not original-document parsing, clinical compliance, GDPR certification, or E2E de-identification assurance.

## Verify / run

```bash
uv run redact-bench check-data --dataset data/ambiguous/cases.jsonl
uv run redact-bench audit-data --dataset data/ambiguous/cases.jsonl
uv run redact-bench suite --config config/suite-ambiguous.yaml --no-ensure-models
```

The suite runs both local Qwen finalists sequentially with the **whole-response cache disabled** and **quality-only mode** (no latency repeats). Runtime depends on the Mac and model loading. Results are stored under `results/suites/<suite-id>/quality/`, visible in the local React UI; no automatic model execution occurs on GitHub CI.

## Reading scores responsibly

Use recall on positives and **false-positive case rate on gold-empty negatives** separately. A single combined F1 cannot show whether a model over-redacts all benign mentions. Macro scores need to account for semantic contrast families; never combine sample sizes from this dataset with the mass Excel benchmark. To avoid overfitting to these frozen cases, reserve a new held-out set for future prompt or rules optimization.
