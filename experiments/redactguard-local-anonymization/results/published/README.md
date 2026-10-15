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
Once runs are COMPLETE, reviewed, and generated from the **same checked-out source commit**, export allowlisted **aggregate metrics only**:

```bash
python3 scripts/publish_portfolio_summary.py --source-ref "$(git rev-parse HEAD)" \
  --run results/<reviewed-healthcare-run> \
  --run results/<reviewed-ambiguous-run> \
  --run results/<reviewed-challenge-run> \
  --approve-public-aggregates \
  --output results/published/portfolio-summary.json
```

Check the source dataset, sample coverage, license, privacy, contract, execution status, model versions, and hardware/provenance before committing.
The exporter rejects missing/partial/contract-failed model summaries and never copies raw inputs, annotations, predictions or case-level evidence.

The portfolio presents dataset coverage separately from PII recall, precision, system leakage and p95 latency. It never replaces missing metrics with placeholder scores.

The `--run` flag can be repeated for different model/dataset cohorts. The exporter checks
the recorded `benchmark_commit` against `--source-ref`, the complete dataset
case count and every model's evaluated/failure coverage. It rejects duplicate
model/dataset pairs instead of silently picking a favorable run. It preserves
a non-sensitive run identifier, contract digest, provider, date, host type and
same-run cohort ID. Model results from separate cohorts must **not** be
represented as one controlled Pareto frontier.

The homepage only computes exploratory system-recall/p95 Pareto points among
two or more models inside the same complete run. The model × dataset matrix
shows standalone scores by dataset; a missing score is not zero.

To publish old runs whose `benchmark_commit` differs from the current repository,
check out that exact commit before exporting. Never fake source provenance.
