#!/usr/bin/env bash
# Bounded static guards; individual benchmark workflows still own all substantive suites.
set -euo pipefail

bash -n experiments/redactguard-local-anonymization/scripts/run_realistic_local.sh
python3 -m compileall -q \
  packages/benchmark-core/src/benchmark_core/persistence \
  packages/benchmark-core/src/benchmark_core/runner \
  experiments/model-capability-benchmark/src/model_capability_bench/runner
