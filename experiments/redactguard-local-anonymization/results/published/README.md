# RedactGuard public benchmark evidence

The current `portfolio-summary.json` contains **real reviewed aggregate model measurements**
imported from a user-provided local `results.zip` (SHA-256
`b35b31d37e779fbf02e76c354f5f3d35f2177ca5a7ee86401c9fbbb2bb9cd39b`).

The ZIP and all raw cases, PII, documents, failures, logs and model outputs
remain **private and uncommitted**. Only 16 aggregate model/dataset
measurements from 6 selected evaluation-v3 quality runs are versioned.

This is **not** a controlled global leaderboard: within Healthcare and Ambiguous,
Qwen and Nemotron groups come from different suites and benchmark commits.
The website's Pareto uses only models inside a matching quality-run cohort.
Observed p95 latency is derived from quality requests, **not** from repeated
latency experiments. Inference failures are included in system-level metrics.

It is generated from committed `data/...` sources, including the realistic annotation summary.
Counts: smoke 20, healthcare 48, ambiguous 48, challenge 46, document E2E 5, realistic 11 documents / 1,566 annotated spans.

Original inference run directories remain gitignored. The public JSON now contains
real aggregates, while GitHub Actions still performs code validation rather than
rerunning the local models.

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

## Regenerate from the original reviewed archive

Use the **dataset-only catalog from before this publication** as
`/tmp/redactguard-dataset-catalog.json`, and the original
`results.zip` (archive SHA-256 above). Do not pass the already
populated portfolio summary as the catalog: the importer deliberately
rejects overwriting published measurements.

```bash
cd experiments/redactguard-local-anonymization
python3 scripts/publish_archived_results.py \
  --archive /private/path/results.zip \
  --catalog /tmp/redactguard-dataset-catalog.json \
  --run-id 20261012T090358Z-suite-d1ff4d13 \
  --run-id 20261012T193156Z-suite-34584908 \
  --run-id 20261012T193357Z-suite-6c13b7b2 \
  --run-id 20261013T081117Z-suite-39803d12 \
  --run-id 20261013T081358Z-suite-39ba2ab2 \
  --run-id 20261013T082146Z-suite-6c00207c \
  --output results/published/portfolio-summary.json
```

The importer only reads manifest/metrics aggregates from those exact v3
quality directories, demands complete dataset attempts, validates metrics
and hashes, and never extracts the archive. Older v2 runs, partial 1/4/5-case
runs, repeated-latency-only runs and backup duplicates were excluded.

### Interpreting the results

- **System recall** includes end-to-end failures; model-only `pii_recall`
  excludes failed inference and can appear much higher.
- **System leakage** is a benchmark-defined risk proxy, not a guarantee
  that the product cannot leak real-world PII.
- **Observed p95** is the quality-run response tail. Avoid presenting it as
  repeated benchmark-grade latency.
- **Run success rate** is the fraction of cases with valid inference.
- Realistic documents are machine-annotated and have not undergone independent
  human adjudication.
