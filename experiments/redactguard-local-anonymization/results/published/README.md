# RedactGuard public benchmark evidence

`portfolio-summary.json` is a **dataset coverage** snapshot, not a model ranking.

It is generated from committed `data/...` sources, including the realistic annotation summary.
Counts: smoke 20, healthcare 48, ambiguous 48, challenge 46, document E2E 5, realistic 11 documents / 1,566 annotated spans.

No model inference metrics are currently versioned under this repository's `results/` directory on `dev`.
GitHub Actions currently runs checks/build/unit tests; this is not evidence that inference models were evaluated.

## Regenerate

```bash
cd experiments/redactguard-local-anonymization
python3 scripts/publish_portfolio_summary.py --source-ref "$(git rev-parse HEAD)" \
  --output results/published/portfolio-summary.json
```

## Publishing measured model runs

The local React dashboard reads live runs under `results/` and is intentionally independent of GitHub.
Once a run is COMPLETE and publicly reviewable, export allowlisted **aggregate metrics only**:

```bash
python3 scripts/publish_portfolio_summary.py --source-ref "$(git rev-parse HEAD)" \
  --run results/<reviewed-complete-run> --approve-public-aggregates \
  --output results/published/portfolio-summary.json
```

Check the source dataset, sample coverage, license, privacy, contract, execution status, model versions, and hardware/provenance before committing.
The exporter rejects missing/partial/contract-failed model summaries and never copies raw inputs, annotations, predictions or case-level evidence.

The portfolio presents dataset coverage separately from PII recall, precision, system leakage and p95 latency. It never replaces missing metrics with placeholder scores.
