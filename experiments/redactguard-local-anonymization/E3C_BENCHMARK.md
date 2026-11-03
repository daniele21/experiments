# E3C Italian clinical-context benchmark

This is an **opt-in, local-only** evaluation of RedactGuard on published Italian
clinical narratives from the [E3C corpus](https://github.com/hltfbk/E3C-Corpus).
It is NOT an independently annotated clinical de-identification benchmark.

## Evidence and rights

- Upstream: FBK E3C-Corpus, release `v2.0.0`, Git commit
  `f74bdf9eaaef7f08437d0c5b930c6dbbc25bbffc`.
- Layer 1 Italian: **86** source JSON texts and matching clinical XML annotation
  files. The official split lists **36 train** IDs; the other **50** are held-out
  test cases. No train text is used as a scored test case.
- The original XML annotations are **medical concepts**, not a complete PII gold.
  Their existence is checked but they are not converted to PII ground truth.
- License: E3C upstream states **Creative Commons Attribution–NonCommercial
  (CC BY-NC)**. Check the applicable license and permissions before commercial use.
  Cite E3C/FBK in publications. The generated clinical text remains upstream
  licensed, even with synthetic additions. Do not redistribute the derived JSONL
  or raw run artifacts as open/public results.
- E3C can contain personal-looking details in its published case narratives;
  no assumption of de-identification or data subject consent is made here.

## Prepare once

From `experiments/redactguard-local-anonymization`:

```bash
uv sync --extra dev
uv run redact-bench prepare-e3c --download
uv run redact-bench check-data --dataset data/cache/e3c-it-v2/synthetic_pii.jsonl
uv run redact-bench audit-data --dataset data/cache/e3c-it-v2/synthetic_pii.jsonl
```

The download is a shallow, sparse Git checkout at `data/cache/e3c-source`. It
retrieves only Layer 1 Italian text, matching annotation XML and split
documentation. The pinned commit SHA is checked before generating outputs.

Alternatively, use a pre-existing **pinned E3C checkout**:

```bash
uv run redact-bench prepare-e3c --source-dir /absolute/path/to/e3c
```

The preparer fails closed on an incorrect tag/SHA, missing XML counterparts,
incomplete split, duplicate IDs, missing source texts or incorrect offsets.

Outputs are git-ignored and deterministic:

| Local file | Documents | Intended use |
| --- | ---: | --- |
| `data/cache/e3c-it-v2/clinical_context.jsonl` | 50 | Original clinical text, **no PII labels**; diagnostic reference only |
| `data/cache/e3c-it-v2/synthetic_pii.jsonl` | 50 | Original context plus six **synthetic, offset-annotated** identity fields per text |
| `data/cache/e3c-it-v2/manifest.json` | 50 | Source tag/SHA, split, original byte/text SHA-256, injected text SHA-256, injection positions |

The injected fields are: person name, patient identifier, email, phone, address
and date of birth. There are **300 targeted synthetic gold spans**. They are
placed at deterministic positions early, midway and late in the case text.
The clinical narrative's original content is preserved. The generator is
versioned as `e3c_it_v2_injected_pii_v1` and the source document family ID
allows paired audit by case.

## Run with the same Korgis pipeline as other benchmark suites

```bash
# Expects Korgis and the selected local GGUF files to be available.
uv run redact-bench suite --config config/suite-e3c.yaml \
  --models qwen3.5-4b-q4km,qwen3.5-9b-q4km

# Or target an already running Korgis directly:
uv run redact-bench compare \
  --dataset data/cache/e3c-it-v2/synthetic_pii.jsonl \
  --models qwen3.5-4b-q4km

uv run redact-bench ui
```

All existing preflight checks, segmented inference, postprocessing, raw case
results, run identity, model identity, failure reasons, system vs model recall,
leakage and latency measurement remain in effect. To add a different model,
override `--models` as for any other RedactGuard suite.

The local UI exposes **E3C · Synthetic PII** as a separate dataset in the
model-by-dataset matrix and dataset detail. The document view can load the
canonical generated text only from the exact local cache allowlist and validates
it against the observed input hash. No public source bytes are committed.

## Measurement interpretation — critical

E3C original clinical texts have **incomplete PII coverage**, so predictions
outside injected fields cannot be judged as false positives or over-redaction.
The original `clinical_context.jsonl` is deliberately **rejected by scored
dataset loaders**, instead of treating zero annotations as zero PII.

For `synthetic_pii.jsonl`, the scoring scope is `injected_only`:

- **Valid**: injected-PII exact/overlap recall, targeted character leakage,
  targeted zero-leak document rate, per-synthetic-type recall, system recall
  including failed inference, validity and observed latency.
- **Not valid / shown as N/A**: full-document PII precision, F1, false-positive
  rate, full-document over-redaction rate, clinical-content preservation, or
  any claim that the entire real case was de-identified.
- Predictions outside the six inserted spans are recorded as **unscored**,
  not false positives. No original E3C clinical entity is treated as a
  negative label or automatically relabelled as PII.
- The currently pinned `healthcare` profile explicitly treats medical
  conditions/treatment/results as sensitive. A future **identity-only** policy
  plus separately reviewed clinical preservation spans is needed to measure
  retention of clinical terms without conflicting policy definitions.

All comparisons must use the same dataset version, profile, inference contract,
segmentation and device/runtime identity. If developing prompts/models, use a
separate development split; the official 50-case test is reserved for final
evaluation. Repeated tuning on the 50 cases forfeits a truly held-out claim.

## Publishing and privacy

Only publish **aggregate metrics and counts** with attribution and explicit
`injected_only` limitations, not case text, raw model responses, spans with
original context, JSONL, screenshots revealing clinical narrative, or
unreviewed model findings. `results/` and the E3C cache contain potentially
sensitive or licensed text and should stay local. The cloud GPT-6 reference
command only allowlists three fully synthetic datasets; **E3C is not an allowed
cloud dataset**.
