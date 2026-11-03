# Public clinical gold: 200 Spanish + 50 Italian cases

These two benchmarks test **clinical entity recognition**, NOT the ability to
decide which patient-specific medical details should be redacted. Do not
average these scores with PII/PHI datasets (ASQ-PHI, MEDDOCAN or E3C injected
PII), and do not call a NER score an anonymization benchmark result.

## 1. SPACCC-Spanish-NER: 200 independently annotated clinical cases

Two distinct publicly released CC BY 4.0 Hugging Face datasets are required:

- IEETA/SPACCC-Spanish-NER — **test** annotations with filename, label,
  start_span, end_span, text (the text field is the entity mention,
  not the full document).
- IEETA/SPACCC-documents — full narratives with filename and document.
  Originals live under a train-named split; this is **not** NER annotation
  training data. Do not fetch the separate annotation train split.

Commands (from experiment directory):

    uv sync --extra dev
    uvx --from huggingface_hub hf download IEETA/SPACCC-Spanish-NER --repo-type dataset --include 'data/test-*.parquet' --local-dir data/cache/medical-sources/spaccc/annotations
    uvx --from huggingface_hub hf download IEETA/SPACCC-documents --repo-type dataset --include 'data/train-*.parquet' --local-dir data/cache/medical-sources/spaccc/documents
    uv run --with pyarrow redact-bench prepare-spaccc --limit 200
    uv run redact-bench check-data --dataset data/cache/spaccc-clinical-gold-v1/cases.jsonl
    uv run redact-bench audit-data --dataset data/cache/spaccc-clinical-gold-v1/cases.jsonl --profiles config/profiles-medical-gold.yaml
    uv run redact-bench suite --config config/suite-spaccc-clinical.yaml

If file names differ, pass --annotations PATH and --documents PATH explicitly
to prepare-spaccc. Every annotation is validated at its source offset.
Documents with invalid annotations are excluded with recorded reasons;
if fewer than 200 good test documents are available the importer fails closed.
Selection is deterministic (seed 20261103), with a content fingerprint and
source SHA256. The program does not commit corpus text to Git or CI.

Gold categories: clinical_disease, clinical_symptom, clinical_procedure,
clinical_chemical, clinical_protein. CHEMICAL is not always patient medication.
Preserve multicategory overlapping source annotations, deduplicate exact
duplicate rows only.

## 2. E3C Layer 1: 50 Italian cases with manual clinical gold

Uses the same E3C pinned checkout as PR #126 (v2.0.0,
f74bdf9eaaef7f08437d0c5b930c6dbbc25bbffc; CC BY-NC).

    uv run redact-bench prepare-e3c --download
    uv run redact-bench prepare-e3c-clinical
    uv run redact-bench check-data --dataset data/cache/e3c-it-clinical-gold-v1/cases.jsonl
    uv run redact-bench suite --config config/suite-e3c-clinical.yaml

The importer verifies the official 36/50 Italian split, Git SHA, text stored
in the XML UIMA Sofa, and exact span offsets (including UTF-16 offsets).
Native labels retained: CLINENTITY (UMLS clinical disorders), BODYPART,
RML (results and measurements), ACTOR (patient / clinician / other actors).
Temporal EVENT is excluded: a verb/event isn't necessarily a treatment.

CLINENTITY does not specifically mean "diagnosis", and ACTOR does not
equate to a named patient or personal identifier. No person-disease links
or redaction policy labels are inferred from the annotated spans.

## Results and limitations

    uv run redact-bench ui

- Both are opt-in, local Korgis suites; defaults are Qwen3.5 4B and 9B.
- Scores measure clinical NER only. They do NOT measure contextual PII
  privacy or production RedactGuard anonymization accuracy.
- The current scoring logic allows type-matched overlapping spans as TP.
  It is not equal to academic exact-match official leaderboard F1.
- Run output versions include stable dataset-selection fingerprints; never
  merge different source subsets into one measurement.
- The code and CI do not run real model inference; use the Mac for actual
  benchmark scores.
- Published case narratives should not be sent to cloud models or exposed
  in public run artifacts without additional privacy/licensing review.
- CARMEN-I on PhysioNet remains restricted and is not downloaded here.
