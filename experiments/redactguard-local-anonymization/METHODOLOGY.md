# Methodology

## Evaluation unit

A case consists of source text, one RedactGuard profile and gold PII spans.

For every case:

1. the frozen RedactGuard profile builds the system prompt;
2. the benchmark calls Korgis `POST /v1/chat/completions`;
3. the model returns `pii_fields[].value` + `pii_type`;
4. deterministic RedactGuard-compatible code resolves each proposed value back to all source occurrences;
5. the resulting spans are compared with gold spans.

This separates model behavior from deterministic redaction behavior and mirrors the current RedactGuard detector contract.

## Primary privacy metrics

- **PII recall**: matched gold entities / total gold entities.
- **Leakage rate**: gold PII characters left uncovered / total gold PII characters.
- **Zero-leak document rate**: share of valid cases with no missed PII characters or entities.
- **Precision**: matched predicted entities / predicted entities.
- **Over-redaction rate**: predicted characters outside gold PII / total non-PII characters.
- **Span F1**: entity-level F1; exact matches are preferred, same-type overlapping spans are accepted as secondary matches.

A benchmark report should show these dimensions independently. v0.1 does not collapse them into one opaque score.

## Output robustness

A request is valid only when:

- Korgis returns successfully;
- the response content is valid JSON;
- `pii_fields` is a list;
- deterministic post-processing completes.

Hallucinated model values that do not exist in the source text are not redacted. They remain visible in the raw result for diagnosis and can indirectly reduce precision/coverage evidence.

## Latency

Latency is client-observed wall clock around `chat.completions.create`.

Model load/activation is **not** part of per-case inference latency. Lifecycle switching belongs to Korgis control-plane evidence and is recorded separately through runtime identity/operations when needed.

For benchmark-grade latency evidence, use a fixed stratified subset with at least 5 warmups and 30 measured repeats per input shape. The default smoke command uses one warmup only because it is an integration check.

## Reproducibility

Every run freezes:

- benchmark code commit when available;
- RedactGuard source contract SHA;
- Korgis tested SHA;
- Korgis `local-llm-identity-v1` payload per model;
- model registry key;
- quantization/backend evidence exposed by Korgis;
- host OS/machine/Python;
- dataset path and case count;
- warmup count.

Do not infer quantization from filenames. The runtime identity is authoritative.

## Model lifecycle

The comparison uses Korgis admin APIs to activate one model at a time. This permits larger model matrices without requiring all artifacts to remain resident simultaneously.

Korgis remains a separate service. The benchmark must never import `local_llm_server` internals or spawn a hidden alternate inference backend.

## Benchmark tiers

### Smoke

Committed deterministic examples. Goal: validate integration, scoring and obvious regressions.

### Quality

Externally labelled generic PII + RedactGuard-specific domain cases. Goal: model-selection evidence.

### End-to-end PDF

PDF -> extraction/preprocessing -> PII detection -> final redaction. Goal: product-system evidence. This tier must stay separate from core model-quality numbers so Docling/extraction errors are not attributed to the LLM.
