# MCB-5 — Dataset Registry and Dataset Adapters

Status: **IMPLEMENTED; CI validation pending**.

## Goal

Separate dataset provenance, loading, caching, normalization and sampling from task logic.

MCB-4 established that a task receives a normalized `Sample`. MCB-5 now owns the path
from a versioned dataset definition to those samples:

```text
DatasetSpec
    ↓
DatasetPluginRegistry
    ↓
BenchmarkDataset.load(context)
    ↓
DatasetLoadResult
    ↓
tuple[Sample, ...]
    ↓
BenchmarkTask
```

The central runner does not know how BANKING77, CLINC150 or a repository-authored fixture
is stored.

## Shared benchmark-core contracts

`benchmark_core.datasets` introduces:

- `DatasetSpec`;
- `DatasetProfileSpec`;
- `DatasetLoadContext`;
- `DatasetLoadResult`;
- `BenchmarkDataset` protocol;
- `DatasetPluginRegistry`;
- `DatasetRegistry`;
- strict dataset/profile YAML loaders;
- cached URL materialization;
- SHA-256 source-file hashing.

### DatasetSpec

Every dataset declares:

- dataset id and version;
- adapter id;
- canonical source;
- pinned revision;
- split;
- license identifier;
- normalized sample schema version;
- cache mode;
- adapter options.

This provenance is configuration, not Python constants.

### DatasetLoadResult

Every load records:

- selected normalized samples;
- number of available candidate samples;
- SHA-256 fingerprint of the ordered selection;
- SHA-256 checksums of source files actually used;
- adapter metadata.

Sample IDs must be unique.

## Profiles are configuration

`profiles.yaml` owns dataset sample limits.

Current profiles:

| Profile | BANKING77 | CLINC150 OOS | Structured output |
|---|---:|---:|---:|
| smoke | 77 | 50 | all |
| budget | 154 | 100 | all |
| standard | 770 | 500 | all |
| full | all | all | all |

BANKING77 smoke deliberately uses at least one example per official class rather than a
generic 20-case subset.

No adapter contains `if profile == ...`.

## BANKING77 adapter

Source:

- `PolyAI-LDN/task-specific-datasets`;
- revision `9d081458ff52e53cf7e848f414e6e9344e4e6696`;
- official `banking_data/test.csv`;
- official `banking_data/categories.json`;
- license metadata: CC BY 4.0.

Behavior:

- downloads into the gitignored cache only when bytes are absent;
- validates the official CSV header and category list;
- validates that every row category belongs to the category file;
- performs deterministic class-balanced sampling;
- uses stable source-index-based sample IDs;
- puts the full label space in normalized sample metadata;
- records checksums for both source files.

The adapter outputs `Sample.expected = <intent label>`, which is directly consumed by the
MCB-4 intent-classification task.

## CLINC150 OOS adapter

Source:

- `clinc/oos-eval`;
- revision `48a0e1cff8f43dd4d0836ecb4ed5df08733e3d2e`;
- split `oos_test`;
- license metadata: CC BY 3.0.

The existing Jev benchmark conservatively removes examples containing obvious
finance/banking terms before using CLINC150 as independent OOS evidence.

MCB-5 preserves that behavior but moves the exclusion vocabulary into `datasets.yaml`.
The Python adapter contains no hidden finance-term list.

Normalized samples use:

```text
expected = "other"
metadata.oos = true
metadata.source_label = original CLINC label
```

The OOS adapter is available now; composition with BANKING77 for calibration belongs to
the capability-suite/evaluator workstream rather than the dataset loader.

## Controlled structured-output dataset

`data/structured-output-controlled-v1.yaml` is repository-authored and versioned with the
benchmark.

It contains 12 deterministic extraction cases covering strings, numbers, integers and
booleans across invoices, support, products, transactions, travel, meetings and other
simple domains.

Each case declares its own response schema. The adapter normalizes that schema into
`Sample.metadata["response_schema"]` for the MCB-4 structured-output task.

The source file itself is checksummed on every load.

## Public-data policy

Public upstream bytes are **not committed**.

The committed catalog contains the pinned upstream URLs/revisions, while bytes live under:

`experiments/model-capability-benchmark/data/cache/`

which is already covered by the repository gitignore.

Tests do not depend on network access: they pre-populate the cache with minimal fixture
files and exercise the real adapters against those files.

## Reproducibility

For every load:

1. source identity and revision come from `datasets.yaml`;
2. source bytes are hashed;
3. sampling uses the shared isolated seeded RNG;
4. stable sample IDs identify selected source rows;
5. ordered sample IDs are hashed into a selection fingerprint;
6. profile and seed are explicit inputs.

This makes it possible for a future run manifest to answer both:

> Which upstream bytes were used?

and:

> Which exact subset/order was selected?

## Operational inspection

`scripts/dataset_inspect.py` supports two modes.

Catalog-only validation without downloads:

```bash
uv run python scripts/dataset_inspect.py --datasets all --profile smoke
```

Load/materialize a selected dataset:

```bash
uv run python scripts/dataset_inspect.py \
  --datasets structured-output-controlled-v1 \
  --profile smoke \
  --load
```

Selecting BANKING77 or CLINC150 with `--load` materializes the pinned source files into
the cache when needed.

## Cross-registry consistency

The MCB-5 integration tests verify that every dataset ID declared as compatible by
`tasks.yaml` exists in `datasets.yaml`.

This prevents a task catalog change from silently referring to a missing dataset.

## Definition of Done

- [x] generic dataset adapter protocol exists;
- [x] strict dataset registry exists;
- [x] strict profile catalog exists;
- [x] source revision/split/license/cache metadata is explicit;
- [x] source checksums and selection fingerprints are recorded;
- [x] BANKING77 uses the new dataset registry;
- [x] BANKING77 sampling is deterministic and class-balanced;
- [x] CLINC150 OOS uses a dedicated adapter with configured overlap filter;
- [x] controlled structured-output dataset exists and is versioned;
- [x] public dataset tests require no network access;
- [x] task-compatible dataset IDs are cross-validated;
- [x] dataset inspection/load CLI exists;
- [ ] focused MCB-5 CI passes;
- [ ] previous MCB/VLM/image-generation gates remain green;
- [ ] full Jev characterization suite remains green.
