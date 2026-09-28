# RedactGuard benchmark remediation and product-alignment plan

Status: planned  
Scope: `daniele21/redact-guard`, `daniele21/experiments`, conditional `daniele21/korgis`  
Reason: current benchmark evidence can conflate inference-contract failures with model-quality failures.

## Objective

Make RedactGuard's PII detection contract robust in production, and make the
`redactguard-local-anonymization` experiment measure that contract without silently
turning transport/parsing/truncation failures into false negatives.

The target separation is:

```text
redact-guard
  owns: PII policy + prompt/output contract + segmentation + parsing +
        span resolution + production failure semantics

experiments
  owns: datasets/gold + benchmark orchestration + preflight + scoring +
        model comparison + provenance + reports/UI

korgis
  owns: runtime/backend execution + structured-output compatibility +
        typed backend/runtime failures
```

A benchmark must consume a pinned RedactGuard detection contract. It must not
silently invent a second prompt or a second post-processing policy.

---

## Findings that trigger this plan

### 1. Invalid inference currently looks like model recall failure

The experiment provider catches every exception and returns `valid=false` with
`findings=[]`. The scorer can then produce 0% recall / 100% leakage even when the
model was never successfully evaluated.

A related presentation artifact is 100% precision with zero predictions.

### 2. RedactGuard itself currently fails open at the parser boundary

`anonimizer/utils/json_utils.py::parse_llm_response` logs invalid JSON and returns
`{"pii_fields": []}`. In the product, malformed model output can therefore be
indistinguishable from a legitimate "no PII found" response.

For a privacy product, those states must remain distinct.

### 3. The current model output contract is unnecessarily verbose

For every detected value the prompt requests:

- `field_name`
- `field_description`
- `pii_type`
- `value`
- `redacted_value`

Most of these values can be derived deterministically from the PII profile. The
verbosity materially increases output-token pressure.

### 4. Large benchmark documents do not match the product execution unit

RedactGuard production analyzes a document page by page. The model-only realistic
benchmark currently sends a whole canonical document as one case.

Large tabular examples can contain tens or hundreds of unique PII values. A single
bounded structured response can be truncated even when the model detects the values
correctly.

### 5. Product policy and benchmark gold are not guaranteed to be identical

For example, the realistic financial gold currently includes business VAT numbers,
invoice identifiers and record identifiers under `account_number`, while the product
prompt also says not to include clearly public/non-personal information.

Policy must be decided in RedactGuard first. Gold must follow that decision, rather
than changing the product prompt only to improve benchmark scores.

---

# Repository ownership

## Changes that belong in `redact-guard`

### RG-1 — Version the production detection contract

Create one explicit contract version, e.g. `redactguard-detection-v2`, covering:

- supported PII types and their semantics;
- prompt instructions;
- structured output schema;
- segmentation/chunking rules;
- value-to-span resolution rules;
- failure semantics;
- deterministic redaction placeholder derivation.

The version must be visible in logs/evidence and exportable for external evaluation.

**Why product-owned:** this defines what RedactGuard actually means by a successful
PII detection.

### RG-2 — Replace silent parser fallback with typed failure

Current invalid JSON behavior must no longer become an empty detection result.

Introduce typed states such as:

```text
success
transport_error
backend_error
invalid_json
invalid_schema
truncated_output
span_resolution_warning
```

A malformed response must surface an analysis failure/warning to the API/UI and must
not be cached as a successful zero-PII result.

**Acceptance:** a deliberately malformed LLM response cannot produce a normal
`has_pii=false` result.

### RG-3 — Make the LLM output schema minimal

The preferred model-facing item should contain only fields needed from the model:

```json
{
  "pii_fields": [
    {
      "pii_type": "private_person",
      "value": "Mario Rossi"
    }
  ]
}
```

Derive product presentation fields deterministically:

- `field_name` from the PII type/profile label;
- `field_description` from the active PII definition;
- `redacted_value` from a deterministic placeholder policy.

Do not ask the model to generate metadata RedactGuard already knows.

**Expected effect:** materially smaller responses and less truncation risk.

### RG-4 — Validate model output against an explicit schema

Define a typed/Pydantic response contract and validate:

- top-level object;
- `pii_fields` array;
- allowed `pii_type`;
- non-empty `value`;
- optional bounded item count if required.

Prefer a Korgis structured-output request that expresses this schema when supported,
while retaining application-level validation after inference.

Backend structured-output support must never replace application validation.

### RG-5 — Preserve inference diagnostics

The RedactGuard internal inference result should retain at least:

- requested model;
- success/failure status;
- HTTP/backend failure category;
- raw final content when locally safe to retain;
- finish/termination reason;
- prompt/completion token counts when available;
- latency;
- parsed item count;
- resolved/unresolved item count;
- cache hit.

The public end-user API need not expose raw sensitive text by default.

### RG-6 — Add bounded segmentation for oversized analysis units

Keep page-level processing as the product semantic unit, but add deterministic
sub-chunking when a page exceeds the configured inference budget.

Requirements:

- deterministic boundaries;
- configurable size;
- bounded overlap only when required;
- mapping of chunk-local spans back to page offsets;
- de-duplication across overlapping chunks;
- one merged page result.

This protects the product from unusually long pages without changing the normal
page-based UX.

### RG-7 — Resolve PII policy ambiguities

Review profile semantics, especially financial/legal identifiers:

- business VAT numbers;
- invoice numbers;
- customer/record identifiers;
- transaction/event dates;
- standalone locations;
- public company/contact information.

For each category choose explicitly:

```text
always sensitive
sensitive only in a personal/account context
not RedactGuard PII
```

Update profile descriptions/examples and version the contract.

**Important:** the experiment gold is updated only after this product-policy decision.

### RG-8 — Add product contract tests

At minimum:

- malformed JSON is not treated as no PII;
- schema-invalid JSON is a typed failure;
- empty valid `pii_fields` remains a valid zero-detection response;
- deterministic metadata derivation;
- repeated-value span resolution;
- unresolved model values are observable;
- oversized page segmentation + offset merge;
- cache does not store failed inference as success.

---

## Changes that belong in `experiments/redactguard-local-anonymization`

### EXP-1 — Rich inference evidence instead of `valid + findings`

Extend benchmark evidence so every case records stages independently:

```text
transport
  -> output contract
  -> parsing/schema
  -> span resolution
  -> quality scoring
```

Store fields such as:

- `inference_status`;
- `http_status` when available;
- `error_type` / bounded error detail;
- `raw_content` for local result artifacts;
- `finish_reason`;
- input/output token counts;
- `predicted_items_raw`;
- `resolved_items`;
- `unresolved_items`;
- latency.

### EXP-2 — Never report model-quality metrics for invalid inference as if valid

Separate two views:

**Model quality**
- computed only from cases with a valid inference/output contract.

**System effectiveness**
- includes execution failures and may conservatively treat a failed detection as
  fully leaked, but must be labelled as an end-to-end/system metric.

Add first-class metrics:

- inference success rate;
- transport success rate;
- JSON/schema validity rate;
- truncation rate;
- span-resolution rate;
- evaluated-case coverage.

Quality metrics become `N/A` when no valid cases exist. No more misleading
"precision 100%" for a model that produced no valid predictions.

### EXP-3 — Add per-model preflight

Before a benchmark model enters the main dataset, run a tiny deterministic fixture
with known PII and verify:

1. request succeeds;
2. structured output is returned;
3. output parses against the RedactGuard contract;
4. at least expected values can resolve to source spans;
5. termination is not max-token truncation.

If preflight fails, mark the model:

```text
INFERENCE_CONTRACT_FAILED
```

and do not present normal recall/leakage for it.

### EXP-4 — Pin and consume the RedactGuard contract

Remove hand-maintained semantic duplication where possible.

The experiment should record:

- source repo;
- RedactGuard commit/ref;
- detection-contract version;
- prompt/profile snapshot hashes;
- segmentation settings.

For reproducibility, commit a generated snapshot of the pinned contract under the
experiment rather than depending on a moving remote checkout at run time.

Add a sync/validation command so the snapshot can be intentionally refreshed from
a selected RedactGuard revision.

### EXP-5 — Split benchmark modes

Create two explicit modes.

#### A. `redactguard-fidelity`

Measures the actual product contract:

```text
product segmentation
  -> product prompt/schema
  -> Korgis
  -> product span resolution
  -> merged document evidence
  -> gold scoring
```

Use the same page/chunk behavior as RedactGuard.

#### B. `model-capability`

Measures generic model extraction capability across heterogeneous canonical
documents. Use deterministic bounded chunks and the minimal PII output schema.

Do not describe model-capability results as RedactGuard product performance.

### EXP-6 — Reconcile realistic gold after RG-7

Once RedactGuard PII policy is frozen:

- update annotations that conflict with the product policy;
- keep policy provenance per gold span;
- version the dataset;
- require independent review before treating the revised gold as final evidence.

Do not change gold merely because a model missed an entity.

### EXP-7 — Make truncation visible

Record and surface `finish_reason` / termination reason.

Any `length` / max-token termination on structured output should be classified as
`truncated_output`, not ordinary model extraction failure.

Segmentation should make truncation rare; output-token configuration remains a
secondary guardrail rather than the main fix.

### EXP-8 — Improve span-resolution accounting

Track separately:

- raw model item count;
- values resolved to source spans;
- unresolved/hallucinated values;
- wrong-type values;
- duplicate values;
- final unique findings.

Unresolved predictions must be visible in precision/diagnostics rather than silently
disappearing.

### EXP-9 — Update the React dashboard

The dashboard must show, per model:

- contract/preflight status;
- inference success rate;
- JSON/schema validity;
- truncation count/rate;
- evaluated cases / total cases;
- raw -> resolved prediction funnel;
- quality metrics only when valid;
- source run + RedactGuard contract version.

A failed model should render as:

```text
CONTRACT FAILED
Quality: N/A
Reason: invalid structured output / backend error / ...
```

not as `Recall 0%, Precision 100%`.

### EXP-10 — Quarantine current historical evidence

Runs produced under the old scoring semantics should be labelled
`diagnostic_only` / `legacy-contract` in the dashboard.

They may remain browsable, but must not be selected as the canonical evidence in
the unified comparison once v2 evidence exists.

---

## Changes that belong in `korgis` only if reproduced

Do not change Korgis speculatively.

First run EXP-3 against:

- Nemotron `llama_cpp-python`;
- Qwen 3.5 `llama_server`;
- `json_object`;
- the future minimal/json-schema contract.

If Qwen/llama-server fails at the runtime boundary, open a Korgis-specific change
for the reproduced failure.

Potential Korgis work, only when proven:

- representative structured-output compatibility test for `llama_server`;
- preserve/normalize backend termination reason;
- typed propagation of backend HTTP/error detail;
- capability evidence for supported structured-output modes.

The benchmark must still handle runtime failures correctly even after Korgis is fixed.

---

# Implementation order

## Phase 0 — Freeze misleading evidence

1. Mark current benchmark runs as legacy/diagnostic.
2. Stop interpreting current Qwen 0% recall as model quality.
3. Add UI warning for legacy runs.

No model reruns yet.

## Phase 1 — RedactGuard safety boundary

Implement RG-1 through RG-5 and RG-8 first.

This gives one robust production contract with typed failure semantics and a compact
model-facing schema.

**Gate:** invalid/malformed/truncated output cannot be represented as a normal
zero-PII result.

## Phase 2 — Benchmark correctness

Implement EXP-1, EXP-2, EXP-3, EXP-4, EXP-7 and EXP-8.

**Gate:** a preflight failure produces no model-quality score.

At this point rerun one tiny smoke dataset against Nemotron and Qwen.

## Phase 3 — Execution-unit alignment

Implement RG-6 plus EXP-5.

Validate that product-fidelity evaluation uses the same segmentation contract as
RedactGuard, while model-capability remains an explicitly separate experiment.

## Phase 4 — Policy/gold alignment

Execute RG-7, then EXP-6.

Version the realistic dataset after the policy decision.

## Phase 5 — UX and full rerun

Implement EXP-9 and EXP-10, then rerun the full model matrix.

Only v2 runs satisfying the contract gates should become canonical comparison evidence.

---

# Validation matrix

| Layer | Test | Owner |
|---|---|---|
| Prompt/schema | Minimal valid response | RedactGuard |
| Parser | Invalid JSON != no PII | RedactGuard |
| Parser | Wrong schema -> typed failure | RedactGuard |
| Span resolution | exact/repeated/whitespace/unresolved | RedactGuard |
| Segmentation | chunk offsets + dedup | RedactGuard |
| Korgis request | tiny structured response by model/backend | experiments preflight |
| Runtime compatibility | reproduced backend-specific structured output | Korgis, conditional |
| Benchmark | invalid inference excluded from model-quality score | experiments |
| Benchmark | system metric includes execution failure distinctly | experiments |
| Gold | policy-consistent labels | experiments after RedactGuard policy freeze |
| UI | failed model shows N/A + cause | experiments |

---

# Definition of done

The remediation is complete when:

1. RedactGuard can distinguish valid zero-PII output from inference/parse failure.
2. The model-facing schema contains only information the model must infer.
3. Large input units cannot silently exhaust the structured-output budget.
4. The benchmark preflight catches backend/schema incompatibility before scoring.
5. Model-quality metrics are computed only on valid inference evidence.
6. End-to-end failure risk remains visible through separate system metrics.
7. Product-fidelity evaluation uses the same RedactGuard contract and segmentation.
8. PII policy and realistic gold are explicitly aligned and versioned.
9. The UI never renders a failed model as `0% recall / 100% precision`.
10. Every canonical result identifies RedactGuard contract version, source revision,
    Korgis runtime identity, model/backend identity, dataset version and run status.
