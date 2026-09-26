# RedactGuard benchmark baselines

This directory is reserved for **measured, reproducible benchmark references**. Do not add invented, hand-edited or model-estimated numbers.

## First baseline

The first realistic reference should be created only after running the full configured local-model matrix against:

```text
data/realistic/
dataset_id = redactguard-realistic-documents-v0.1
```

Required quality run:

```bash
uv run redact-bench compare --dataset data/realistic
```

Required latency run:

```bash
uv run redact-bench latency \
  --dataset data/realistic \
  --case-ids lettera.txt,presentazione.pptx,contratto.pdf \
  --warmups 5 \
  --repeats 30
```

## What to preserve

A baseline snapshot should keep:

```text
baselines/<dataset-id>/<baseline-id>/
├── README.md
├── quality/
│   ├── manifest.json
│   ├── metrics.json
│   └── failures.json
└── latency/
    ├── manifest.json
    └── metrics.json
```

The HTML report can be preserved when useful, but the JSON files are authoritative.

Do not copy raw model outputs into the committed baseline unless there is a specific diagnostic reason; raw files may contain document content or PII.

## Baseline identity

The baseline README must record:

- experiment Git commit;
- dataset id/version;
- RedactGuard contract SHA;
- Korgis tested SHA;
- Korgis runtime identity for every model;
- machine/OS architecture;
- model registry keys and quantization evidence;
- quality command;
- latency command;
- whether the gold was human-reviewed.

Latency is only comparable across runs on materially equivalent hardware/runtime configuration. Quality metrics can be compared more broadly, but model/runtime identity must still match.

## Interpreting evaluation v2

Use the views together:

- **micro** answers total annotated-span exposure;
- **macro** answers cross-document consistency;
- **by type** exposes taxonomy-specific weaknesses;
- **by document** exposes layout/context-specific weaknesses;
- **failure analysis** gives the concrete missed and over-redacted spans.

A baseline is a reference point, not an acceptance threshold. Product acceptance criteria should be introduced only after measured distributions and failure modes are reviewed.
