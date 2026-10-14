# Experiments — Coding Agent Guide

## Shared Mac CI (local-runner-infra)

- `daniele21/local-runner-infra` owns the native Mac runner registrations. **Do not** attempt to assign these runners directly via `runs-on` in this repository.
- `.github/workflows/local-ci.yml` submits the exact source SHA through `repository_dispatch`; `.github/ci/local-test.sh` is the bounded source-owned deterministic entrypoint executed on the central Mac runner.
- Observe `local-ci/mac` on the commit and the corresponding central workflow logs, **not** merely the dispatch job's status.
- Existing per-benchmark PR validation and specialist checks remain authoritative. The initial central lane is not their replacement. Never turn missing tools, models, datasets or other required inputs into a false green result.
- Full operating contract: https://github.com/daniele21/local-runner-infra/blob/main/docs/integration-guide.md
