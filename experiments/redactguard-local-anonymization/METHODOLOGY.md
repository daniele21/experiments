# Methodology

## Evaluation unit

The benchmark has two deliberately separate evaluation paths.

### Core text path

A case consists of source text, one RedactGuard profile and gold PII spans.

For every case:

1. the frozen RedactGuard profile builds the system prompt;
2. the benchmark calls Korgis `POST /v1/chat/completions`;
3. the model returns `pii_fields[].value` + `pii_type`;
4. deterministic RedactGuard-compatible code resolves each proposed value back to all source occurrences;
5. the resulting spans are compared with gold spans.

This isolates model behavior from document extraction.

### Document end-to-end path

A document case contains canonical source text per page plus gold PII annotations. Synthetic PDFs are generated deterministically from that source, then processed with the same Docling page-export contract used by RedactGuard.

For every document:

1. generate or provide the PDF;
2. extract each page with Docling;
3. align source gold values to the extracted page text using whitespace-normalized matching;
4. measure extraction quality before calling any model;
5. call each Korgis model on exactly the same extracted text;
6. apply the frozen RedactGuard value-to-source-span post-processing;
7. report both model-only and full pipeline metrics.

Docling runs once per document set, not once per model. This prevents extraction variance from contaminating model comparisons.

## Primary privacy metrics

### Model metrics

- **PII recall**: matched gold entities / total gold entities available in the evaluated text.
- **Leakage rate**: gold PII characters left uncovered / total gold PII characters.
- **Precision**: matched predicted entities / predicted entities.
- **Over-redaction rate**: predicted characters outside gold PII / total non-PII characters.
- **Span F1**: entity-level F1; exact matches are preferred, same-type overlapping spans are accepted as secondary matches.
- **Valid output rate**: share of calls producing usable JSON and deterministic post-processing.

### Extraction metrics

- **Extraction entity recall**: gold PII entities that can still be resolved in Docling output / source gold PII entities.
- **Extraction character recall**: source PII characters represented by successfully aligned entities / source PII characters.
- **Text similarity**: whitespace-normalized source/extracted text similarity, used diagnostically rather than as a privacy score.
- **Missing/extra pages**: page-structure evidence from the extraction layer.

### End-to-end document metrics

- **E2E PII recall**: model true positives / all source gold entities. Gold entities lost by extraction are therefore false negatives.
- **E2E leakage rate**: model-uncovered gold characters plus characters belonging to extraction-lost entities / pipeline gold-character denominator.
- **E2E zero-leak document rate**: share of whole documents where every source gold entity survives extraction and is covered by the final predicted spans.

The report never collapses extraction and model behavior into one opaque score. The end-to-end metrics are shown alongside their components.

## Output robustness

A model request is valid only when:

- Korgis returns successfully;
- the response content is valid JSON;
- `pii_fields` is a list;
- deterministic post-processing completes.

Hallucinated model values that do not exist in the extracted source text are not redacted. They remain visible in raw evidence.

An extraction-missing or empty page is an extraction failure, not a model failure. It is excluded from model-only quality aggregation but still counts against end-to-end privacy metrics.

## Latency

Latency is client-observed wall clock around `chat.completions.create`.

Model load/activation and Docling extraction are **not** part of per-page LLM inference latency. The document run stores extraction evidence independently; lifecycle switching belongs to Korgis control-plane evidence.

For benchmark-grade latency evidence, use the dedicated latency command with a fixed stratified subset, at least 5 warmups and 30 measured repeats per input shape.

## Reproducibility

Every run freezes:

- benchmark code commit when available;
- RedactGuard source contract SHA;
- Korgis tested SHA;
- Korgis `local-llm-identity-v1` payload per model;
- model registry key;
- quantization/backend evidence exposed by Korgis;
- host OS/machine/Python;
- dataset or document-manifest path;
- warmup count;
- document extraction evidence for the PDF tier.

Synthetic PDF bytes are generated from the committed canonical manifest and are intentionally not versioned.

Do not infer quantization from filenames. The runtime identity is authoritative.

## Model lifecycle

The comparison uses Korgis admin APIs to activate one model at a time. This permits larger model matrices without requiring all artifacts to remain resident simultaneously.

Korgis remains a separate service. The benchmark must never import `local_llm_server` internals or spawn a hidden alternate inference backend.

## Benchmark tiers

### Smoke text

Committed deterministic examples. Goal: validate model integration, scoring and obvious regressions.

### Quality text

Externally labelled generic PII + RedactGuard-specific domain cases. Goal: model-selection evidence independent of PDF parsing.

### End-to-end PDF

Implemented in `redact-bench documents`.

PDF → Docling → PII detection → deterministic span resolution. Goal: product-system evidence while retaining extraction/model attribution.

The committed synthetic document set is a smoke tier. A publication-grade document benchmark should add independently reviewed real-world layouts and a held-out split.
