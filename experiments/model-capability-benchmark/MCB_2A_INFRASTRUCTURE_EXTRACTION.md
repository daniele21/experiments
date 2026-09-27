# MCB-2A — Shared Infrastructure Extraction

Status: **IMPLEMENTED; CI validation pending**.

MCB-2A is the first production-code extraction from `jev-vs-llm` into
`packages/benchmark-core`.

The scope is deliberately limited to infrastructure already protected by MCB-0
characterization tests.

## Extracted components

### 1. Environment provenance and manifest serialization

New shared modules:

- `benchmark_core.environment`;
- `benchmark_core.manifests`.

The core now owns:

- git commit lookup;
- Python/platform provenance;
- package-version lookup;
- JSON environment-manifest serialization.

`jev_bench.manifest.write_manifest` remains as a compatibility wrapper and only supplies
the Jev-specific package list.

The existing Jev manifest envelope remains unchanged.

### 2. Run identity

New shared module:

- `benchmark_core.run_identity`.

It owns:

- run id generation;
- run group;
- suite;
- UTC timestamp;
- runner location.

`jev_bench.cli._tag_run` still returns the same DataFrame columns but no longer owns
UUID/timestamp creation.

### 3. CSV persistence

New shared module:

- `benchmark_core.persistence`.

It provides record-oriented append persistence without importing pandas.

The implementation:

- preserves existing rows;
- preserves existing column order;
- extends the schema when new fields appear;
- serializes missing numeric values as empty CSV cells;
- rewrites the logical table so schema extension is safe.

`jev_bench.runner.append_results` remains as a compatibility wrapper converting a
DataFrame to generic record mappings.

## Dependency wiring

`jev-bench` now declares `benchmark-core` as an editable local dependency:

```toml
[tool.uv.sources]
benchmark-core = { path = "../../packages/benchmark-core", editable = true }
```

The committed `uv.lock` includes the local package so documented `uv run --frozen`
commands continue to work.

The pytest-only `pythonpath` bridge from MCB-1 is retained for explicit source visibility,
but it is no longer the only mechanism by which Jev can import benchmark-core.

## Compatibility boundary

The dependency direction is now real at production runtime:

```text
jev-vs-llm
    |
    +--> benchmark-core.manifests
    +--> benchmark-core.run_identity
    +--> benchmark-core.persistence
    +--> benchmark-core contracts/provider protocol

benchmark-core -X-> jev-vs-llm
```

No shared core module imports `jev_bench`.

## Intentionally not extracted in MCB-2A

The following remain for later MCB-2 slices:

- model/provider config loading;
- reusable task runner loop;
- report data model;
- dataset sampling/fingerprinting helpers;
- common pricing hooks;
- transport policy;
- OpenAI-compatible HTTP transport;
- provider error normalization;
- Korgis lifecycle management.

These are higher-coupling changes and should not be mixed with the first infrastructure
migration.

## Validation requirements

MCB-2A is complete when:

- [x] Jev has a real local package dependency on benchmark-core;
- [x] lockfile records that dependency;
- [x] manifest implementation is shared;
- [x] run identity implementation is shared;
- [x] CSV persistence implementation is shared;
- [x] Jev compatibility wrappers preserve public/internal call sites;
- [x] benchmark-core remains independent from Jev;
- [ ] `uv sync --frozen` succeeds;
- [ ] focused core/infrastructure tests pass;
- [ ] full MCB-0 characterization suite remains green.
