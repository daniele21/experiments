# Run the full realistic RedactGuard benchmark locally

This runs the committed `data/realistic` dataset through the managed Korgis suite, with
one model at a time (no runner registration or GitHub Actions required).

## Start from your Mac Terminal

From a Git checkout of `daniele21/experiments` (the script automatically initializes the repository's pinned `korgis/` submodule if it is not populated):

```bash
cd experiments/redactguard-local-anonymization

# Check installed models, dataset, Apple Silicon Python and llama-server.
bash scripts/run_realistic_local.sh --check-only

# Full realistic quality + repeated latency suite, all models in config/suite.yaml.
bash scripts/run_realistic_local.sh

# Full realistic suite, restricted to the two IDs provided here.
bash scripts/run_realistic_local.sh --models "qwen3.5-4b-q4km,qwen3.5-9b-q4km"

# Alternative form: explicitly provide multiple model IDs.
bash scripts/run_realistic_local.sh --model nemotron-nano-4b --model nemotron-nano-4b-q8
```

By default the suite compares the four IDs in `config/suite.yaml`:
- `nemotron-nano-4b`
- `nemotron-nano-4b-q8`
- `qwen3.5-4b-q4km`
- `qwen3.5-9b-q4km`

You can start with a smaller single-model run. The command line's `--models` and `--model` values completely override the YAML model list; no additional models are run:

```bash
bash scripts/run_realistic_local.sh --model qwen3.5-4b-q4km
```

By default, `KORGIS_REPO` points to the **pinned `korgis/` submodule** in the repository root. If the submodule needs initialization, the script runs `git submodule update --init --depth 1 -- korgis`. You can also initialize it beforehand from the repository root:

```bash
git submodule update --init --depth 1 -- korgis
```

To explicitly use a different Korgis checkout, override the pinned submodule:

```bash
bash scripts/run_realistic_local.sh \
  --korgis-repo "$HOME/Personal/korgis"
```

If the wrong llama-server executable is selected, use a version-verified binary:

```bash
bash scripts/run_realistic_local.sh \
  --llama-server-bin /opt/homebrew/bin/llama-server
```

The script **does not download model weights unless explicitly requested**
with `--download-missing`. A missing model fails before benchmarking.

## What the script does

1. Forces the process to native arm64 (avoids x86_64/Rosetta wheel builds).
2. Installs/reconciles Python 3.12 dependencies with `uv` for both projects.
3. Validates the realistic dataset's canonical text and gold spans.
4. Checks the local GGUF models using the Korgis model registry.
5. Verifies an attributable `llama-server` binary meeting Korgis's build floor.
6. Refuses to interfere with an existing service on benchmark port 12435.
7. Executes `redact-bench suite --config config/suite.yaml --models <exact-selected-ids> --no-ensure-models`
   with managed Korgis startup/restart per model. Model selection is passed explicitly, and all cases of the realistic dataset are evaluated for every selected model.

**Full** means the quality suite plus configured repeated latency checks.
This can be compute-intensive. The script avoids concurrent model runs; it
does not impose a hard RAM limit.

## Results and troubleshooting

- Combined suites: `results/suites/<suite-id>/` (quality, latency, manifest)
- History dashboard: `results/dashboard.html`
- Terminal and error log: `results/manual-logs/realistic-<timestamp>.log`
- Managed server logs: `results/suites/<suite-id>/logs/`

You can open the interactive dashboard after installing its UI dependencies:

```bash
npm --prefix ui install
uv run redact-bench ui
```

If the Korgis process exits with `Cannot verify llama-server version`,
the candidate binary may be too old, use an unparseable version format, or
time out during Korgis's version probe even when an earlier check succeeded.
Do not override Korgis's compatibility checks without explicitly reviewing
the resulting runtime/benchmark validity. Try a newer attributable Homebrew
llama-server executable and inspect the local suite's Korgis logs.

The original source documents, PII records, model responses, logs and complete
benchmark artifacts stay on your Mac: this script uploads nothing. Committed
`data/realistic` text fixtures are still benchmark inputs and should be
handled accordingly.
