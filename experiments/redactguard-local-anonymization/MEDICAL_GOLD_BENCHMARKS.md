# Medical benchmark runbook

These are **separate** experiments: do not average scores across them.

| Dataset | Task | Language | Gold |
|---|---|---|---|
| ASQ-PHI | PHI detection | English | 13 HIPAA labels; positive and hard-negative queries |
| MEDDOCAN | PHI detection | Spanish | BRAT annotations, official test split |
| PharmaER.IT | Clinical NER **not PII** | Italian | Gold test: DRUG, DISEASE, SYMPTOM, ANATOMICAL_PART |

All source texts and generated JSONL live in git-ignored `data/cache`.
Benchmarks run through Korgis with *dataset-specific profiles* in
`config/profiles-medical-gold.yaml`. They do not measure the unchanged
production RedactGuard healthcare policy.

## Setup

```bash
cd ~/Projects/experiments
git fetch origin
git switch daniele/feat-medical-gold-benchmarks-20261103
git pull --ff-only
cd experiments/redactguard-local-anonymization
uv sync --extra dev
```

## ASQ-PHI: easiest first test

```bash
uv run redact-bench prepare-medical --dataset asq-phi --download
uv run redact-bench check-data --dataset data/cache/asq-phi-v1/cases.jsonl
uv run redact-bench suite --config config/suite-asq-phi.yaml
```

Downloads official ASQ-PHI (MIT), pinned to GitHub revision
`fdb371ce7e3908a945d82f20411546b9876f862e`.
Default 200 test cases: 160 positives and 40 hard negatives. Change quotas
with `--positives` and `--negatives`. Original 13 PHI categories are kept;
repeated ambiguous values and overlaps are excluded with reasons in manifest.
The source is validated against 1,051 cases and 832 positives.

## MEDDOCAN: Spanish PHI

Acquire the official MEDDOCAN archive from
https://zenodo.org/records/4279323 and extract into
`data/cache/medical-sources/meddocan`. Then:

```bash
uv run redact-bench prepare-medical --dataset meddocan --limit 40
uv run redact-bench check-data --dataset data/cache/meddocan-test-v1/cases.jsonl
uv run redact-bench suite --config config/suite-meddocan.yaml
```

Only test folders are imported. The BRAT parser validates every exact offset,
normalizes explicit granular labels into eight coarse categories, and excludes
unsupported documents with a reason in manifest. Confirm coverage and
exclusions. Original corpus CC BY 4.0; cite the creators.

## PharmaER.IT: Italian terminology, NOT privacy protection

From https://huggingface.co/datasets/expertai/PharmaER.IT download only the
**Gold test** parquet (10 documents), not Silver. Then supply its actual path:

```bash
uv run --with pyarrow redact-bench prepare-medical --dataset pharmaer --source /path/to/test.parquet
uv run redact-bench check-data --dataset data/cache/pharmaer-it-gold-test-v03/cases.jsonl
uv run redact-bench suite --config config/suite-pharmaer.yaml
```

BIO labels and token offsets are strictly checked before any score is shown.
Four clinical labels are evaluated even when appearing in generic medicine
leaflets. These are not necessarily patient-linked sensitive data. The source
card shows inconsistent license identifiers (ODC-BY metadata vs Apache-2.0
prose), so review rights before reuse.

## Inspect and compare

```bash
uv run redact-bench ui
```

Compare models on the **same** dataset version, cases, profile, environment
and scoring protocol. PHI recall, leakage and false-positive rate (on
complete gold) can be analyzed for ASQ/MEDDOCAN. Clinical NER precision,
recall and F1 from PharmaER must never be named PHI anonymization accuracy.
The current scorer counts same-type overlap as matching; its scores are NOT
identical to official strict exact-span leaderboard metrics. Model inference
has not yet been run in this branch, so no real scores are claimed.

MDeID (October 2026) is pending an official public corpus and license.
E3C PR #126 currently evaluates synthetic injected PII, not its native
clinical XML labels.
