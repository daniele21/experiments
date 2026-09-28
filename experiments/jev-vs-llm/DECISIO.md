# Decisio classification experiment

This experiment uses the real Decisio Python scorers and in-process llama.cpp
backend. It does not route Decisio through Korgis's chat endpoint.

## Protocol

- Qwen3.5 2B and 4B, both the existing Unsloth Q4_K_M GGUFs.
- Same 24 committed routing cases, six classes, deterministic order (seed 42).
- Native CPU reference backend, four threads, context 8192, batch/ubatch 512.
- Thinking disabled by Decisio's compiler; one excluded warmup per method.
- `direct`: native letter scorer with question-prefix reuse enabled.
- `fresh`: identical prompt and scorer, shared-prefix execution disabled.
- `json`: Decisio's autoregressive JSON comparator, maximum 64 answer tokens.
- Sequential methods/models, no concurrent inference from this runner.
- Latency includes prompt compilation, scoring/generation and result construction;
  model loading and GGUF hashing are excluded. This is not a CPU-versus-Metal comparison.
- Incorrect, invalid and failed requests remain in the accuracy denominator.
- Scores are uncalibrated preferences, not correctness probabilities.

The direct compiler only accepts 26 candidates. BANKING77 has 77, so it cannot
be evaluated with the unmodified direct scorer. The runner rejects this combination
before loading weights. It supports the native experimental `semantic` scorer for
all 77 alternatives, but that requires candidate-by-candidate scoring and is a
different algorithm. No shortlist based on ground-truth labels is used.

Short routing prompts may not produce any cache hits: the reference backend only
checkpoints complete 512-token chunks. A successful run with zero cache hits is
evidence about classification/readout, not a demonstration of stateful speedup.

## Reproduce

The normal entrypoint is the same launcher used for Korgis:

```bash
uv run python scripts/run_local_matrix.py --provider decisio \
  --models qwen3.5-2b-q4km,qwen3.5-4b-q4km --experiments routing --dataset smoke

uv run python scripts/run_local_matrix.py --provider decisio \
  --models qwen3.5-2b-q4km,qwen3.5-4b-q4km --experiments routing \
  --dataset public --profile budget
```

The launcher displays Rich progress, initialization/warmup phases, elapsed time,
ETA, per-case results and a final comparison table. It uses the benchmark registry,
creates a unique output directory, and starts each inference worker in Decisio's
own environment. Defaults: sibling Decisio checkout, its `.venv/bin/python`, four
CPU threads, `direct,json` for smoke and `semantic,json` for public. Override the
checkout/interpreter using `--decisio-root` / `--decisio-python`.

Use `--resume results/decisio/<session>` to continue a matrix or a legacy single-model
run. Saved settings are inferred; completed cases are skipped. Interrupting the
launcher terminates its worker and preserves completed rows. `--no-progress` uses
plain logs; interactive terminals show bars automatically. Dataset/profile flags
match the Korgis launcher, while the worker's low-level flags below remain available.

Use an existing Decisio environment with its pinned `llama-cpp-python==0.3.35`.
Run from this experiment directory, replacing paths with your checkout and GGUFs:

```bash
/path/to/decisio/.venv/bin/python scripts/compare_decisio.py \
  --decisio-root /path/to/decisio \
  --model /path/to/Qwen3.5-2B-Q4_K_M.gguf \
  --methods direct,fresh,json \
  --output results/decisio/2b-smoke

/path/to/decisio/.venv/bin/python scripts/compare_decisio.py \
  --decisio-root /path/to/decisio \
  --model /path/to/Qwen3.5-4B-Q4_K_M.gguf \
  --methods direct,fresh,json \
  --output results/decisio/4b-smoke
```

New output directories prevent overwriting evidence; the worker also accepts
`--resume` with an existing compatible directory. Each contains:
`fixture.json`, `manifest.json` (Decisio SHA/dirty status, model identity and GGUF
hash, runtime settings), `rows.jsonl` (all decisions, scores, timing, counters and
errors), and `summary.json` (accuracy, macro-F1, validity, p50/p95 and errors).

For the separate, more expensive semantic BANKING77 experiment, prepare public
data with the existing harness first, then add:

```text
--dataset banking77 --cases 77 --methods semantic,json
```

The 77-case profile selects one test example per class using the existing benchmark
sampler. Omitting `--cases` evaluates the entire test set. Smoke results must not
be interpreted as BANKING77 results or compared directly to historical GPU/cloud
latencies.
