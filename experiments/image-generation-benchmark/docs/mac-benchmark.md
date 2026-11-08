# Qwen Image 2.1 Turbo — first Mac benchmark

Status: prepared (2026-11-08). Benchmark owner: daniele21/experiments.
Do not claim a four-image benchmark has executed until the pilot run
finishes and provides validated images. A one-image canary is a separate gate.

## Verified baseline

- Real **native stable-diffusion.cpp** Qwen Turbo smoke passed on the Mac mini
  with local GGUF diffusion, Qwen3-VL GGUF encoder, BF16 VAE.
- [Native proof](https://github.com/daniele21/local-runner-infra/actions/runs/42489592041):
  1024×1024, 8 steps Euler, CFG 1, seed 42, one PNG; generation 177.6 s,
  native process peak RSS 4.92 GiB (not total unified/GPU memory).
- [Pipeline preflight](https://github.com/daniele21/local-runner-infra/actions/runs/42491203756)
  passed with zero inference. Exact profile prompt IDs:
  `text-004`, `comp-004`, `photo-004`, `design-002`.
- Korgis implementation [PR #259](https://github.com/daniele21/korgis/pull/259)
  and Experiments [PR #131](https://github.com/daniele21/experiments/pull/131)
  are still in draft/unmerged form. Their exact reviewed commits are fixed in
  the central workflow.

## Benchmark action

Source-owned script: `experiments/image-generation-benchmark/scripts/run_mac_pilot.sh`.

The central Mac runner invokes this versioned script at the exact pinned
Experiments SHA; central infrastructure owns only checkout, request authorization,
job limits and evidence upload. Korgis only provides inference.

Optional central infrastructure trigger:
`daniele21/local-runner-infra/.github/ci/requests/korgis-qwen-turbo-benchmark.json`.

- `BENCHMARK_MODE=preflight`: resolve source/profile/toolchains and dry-run without image calls.
- `BENCHMARK_MODE=canary` with `BENCHMARK_PROFILE=canary`: run one 1024×1024
  photorealism image through Experiments → Korgis → native Metal. Save a real
  PNG, one evidence row and memory/swap telemetry before attempting a larger batch.
- `BENCHMARK_MODE=pilot` with `BENCHMARK_PROFILE=pilot`: boot pinned Korgis and pinned native Metal sd-server, run
  Experiments `pilot` at four categories × one sample, validate 4 PNGs and
  their evidence rows; archive results. Change the explicit approved request
  from `preflight` to `pilot` on trusted central main to trigger it.
- No paid cloud image-generation models, no model downloads. Existing 10GB
  weights and pinned native binary on runner are reused.
- Workflow has a 40-minute cap and serial execution. Four images at the
  observed native single-image time are roughly 12 minutes of inference,
  but this is an estimate; Korgis overhead, host contention and variation
  are unmeasured. Any failure must be reflected in job status.

## What evidence is saved

The Experiments script creates a versioned output directory. When invoked by
the central self-hosted runner, the GitHub Actions artifact
`qwen-turbo-experiments-pilot-<run_id>` includes:

- `summary.json`: 4/4 validity gate, latency distribution, total wall time,
  runner identification, physical RAM, sampled `sd-server` peak RSS where
  available (RSS does not equal total GPU/unified memory).
- `results/<run>/manifest.json`: suite, profile, model, generation options,
  prompt IDs and repetition count.
- `results/<run>/evidence.csv`: per-prompt latency, seed,
  validity, provider metadata and artifact SHA-256.
- `results/<run>/artifacts/**`: actual generated PNGs for gallery and review.
- `admission-probe.json`: live Mac host-memory admission decision, actual
  measured reclaimable RAM, swap already used and the estimate being reserved.
- `mac_resource_samples.jsonl`: time samples of native process RSS,
  host reclaimable memory, swap in use, cumulative swap-in and swap-out pages.
- `results/<run>/runtime_metrics.json`: telemetry summary also consumed by
  the Experiments React UI under **Memory & swap**.
- `korgis.log`, `models.json`, `dry-run.txt`: debugging provenance.

Retained GitHub artifact for 14 days. A provider-valid PNG is not
evidence of visual correctness. Manually review prompt compliance,
text fidelity, object count, physical plausibility and design quality
using the existing Experiments UI / blind-review flow.

## Gates before increasing scale

1. **Canary 1 image**: verify Korgis API E2E, host guard, successful PNG,
   and paging trend during inference. RSS is not whole-system unified memory.
2. **Pilot 4 images**: four-category output and evidence archive; compare
   latency and paging with the canary.
3. **Review 4 images manually** and fix any model/runtime quality defects.
4. **Robust 60 images/model**: 20 versioned prompts × 3 samples. Running on
   the observed 177.6 s/image would require ~3 hours of inference, excluding
   overhead. The 40-minute workflow must not be used for robust. Add resume,
   bounded checkpoints, explicit authorization and per-batch artifact storage
   before such a run.
5. **Cloud model comparison**: GPT image/Gemini adapters already exist in
   Experiments but currently call provider APIs directly; require explicit
   key configuration and spend controls before enabling paid arms.
