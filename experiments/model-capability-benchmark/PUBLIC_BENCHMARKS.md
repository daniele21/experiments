# MCB public benchmark suite (opt-in)

MCB has two independent suites. **The historical default stays unchanged**:

- `suite.yaml` / `capability-core` v3: 468 controlled/public-label cases, including all previous benchmark revisions.
- `suite_public.yaml` / `capability-public-benchmarks` v1: 140 small, reproducible public benchmark test/validation cases in Core.

Public suite is an **MCB protocol on pinned public data**, **not** the official full dataset leaderboard protocol.
We do not publish a 40-case GSM8K score as an official GSM8K full-test score.

## Sources and provenance

| MCB dataset ID | Upstream | Upstream split | License | Core |
| --- | --- | --- | --- | ---: |
| `gsm8k-main-test` | [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k) | `main/test` (1,319 total) | MIT | 40 |
| `squad-v2-validation` | [rajpurkar/squad_v2](https://huggingface.co/datasets/rajpurkar/squad_v2) | `validation` (11,873 total) | CC BY-SA 4.0 | 60 (30 answerable + 30 unanswerable) |
| `jsonschemabench-github-easy-test` | [epfl-dlab/JSONSchemaBench](https://huggingface.co/datasets/epfl-dlab/JSONSchemaBench) | `Github_easy/test` (577 upstream) | MIT | 40 |

Each source URL in `datasets.yaml` pins a **full immutable upstream commit SHA**, the adapter uses the original Parquet file, and the cached source's SHA-256 is preserved in `source_checksums`. Dataset IDs, revisions, selected source indices, source splits, profiles and selection fingerprints persist in evidence. Case IDs never depend on random order. This requires no new dependency: MCB reads Parquet with its existing DuckDB dependency.

The upstream dataset may have known contamination in pretrained models. Public provenance alone does **not** prove model training independence.

**SQuAD protocol:** MCB asks for JSON `{answer, abstain}`, uses the official SQuAD text normalization (lowercase, remove punctuation, articles and extra whitespace), and accepts every upstream gold alias. It scores `qa_correct`, which requires a correct answer on answerable items and a correct abstention on impossible items. It does not compute the official SQuAD v2 threshold-tuned F1/EM leaderboard metric.

**GSM8K protocol:** MCB extracts the upstream final numeric gold after `####`, normalizes decimals/commas and evaluates the final answer. The original worked solution is not leaked to the prompt. This is an MCB zero-shot JSON-output evaluation, not necessarily prompt-parity with an external published number.

**JSONSchemaBench protocol:** MCB tests JSON Schema compliance, **not** semantic extraction or JSONSchemaBench's official constrained-decoding engine timings/coverage. Its v1 adapter deliberately selects only object-root schemas that satisfy local validator checks, have locally resolvable references and at most 12,000 schema characters. Rejected upstream rows are counted (`source_rows`, `excluded_rows`, `eligible_rows`) to make this reduced subset explicit. Unsupported remote references are never automatically fetched. The upstream dataset has no gold data values: `expected=None` is correct.

## Commands

From `experiments/model-capability-benchmark`:

```bash
uv sync --frozen --extra dev

# Read configuration before downloading anything
uv run --frozen model-bench --suite suite_public.yaml capabilities
uv run --frozen model-bench --suite suite_public.yaml plan --profile core --capabilities all

# Real preflight and cost/latency pilot on one selected model
export MODEL=qwen3.5-2b-q4km
uv run --frozen model-bench --suite suite_public.yaml validate-config --models "$MODEL"
uv run --frozen model-bench --suite suite_public.yaml estimate \
  --models "$MODEL" --profile core --capabilities all --pilot-cases 3

# Distinct run group: never overwrite legacy results
uv run --frozen model-bench --suite suite_public.yaml run \
  --run-group public-benchmarks-v1 \
  --models "$MODEL" --capabilities all --profile core

# Offline projection and dashboard export from immutable run evidence
uv run --frozen model-bench project --rebuild --export-dashboard
```

Existing default commands without `--suite` still run historical `suite.yaml`. Use the same
public suite filename, seed, profile, commit, source artifact and evaluator versions for every compared model.

Case budgets: `smoke = 12+12+12 = 36`, `core = 40+60+40 = 140`,
`extended = 200+200+150 = 550`. Source files are cached and downloaded only on first
load. Estimated run time is model-dependent. `plan` does not contact models or download data;
`estimate` and `run` do.

## Science and interpretation guards

- MCB stores **raw sources and actual selected case fingerprints**, so any same-case paired comparison remains reproducible.
- Do not compare public v1 scores directly to controlled v2/v3 scores, or call them equivalent despite both measuring math or QA.
- Do not give official benchmark leaderboard labels or cite official test totals as run sample counts.
- Report paired `n`, confidence intervals, invalid-output rates and missing resource data separately.
- SQuAD and JSONSchemaBench use different concepts of correctness; aggregating into one undifferentiated score is not recommended.
- JSONSchemaBench's object/root-size/reference filtering must remain versioned and visible, because it affects measured difficulty.
- Before external publication, perform a real-provider smoke + canonical run and review a sample of gold normalization and schema evaluator outputs.

## Recommended follow-on

Add a second JSONSchemaBench subset (`Github_medium`) only after the object-root compliance path passes
real provider validation. Add structured-output **semantic extraction** from benchmark sources separately;
schema compliance alone cannot replace the original controlled extraction suite.
