# Qwen Image 2.1 Turbo — Experiments ↔ Korgis Handoff Plan

Status: READY (planning only; no model benchmark executed)
Date: 2026-11-08
Producer: `daniele21/korgis`, `docs/workstreams/qwen-image-2-1-turbo.md`
Consumer: `experiments/image-generation-benchmark`

## Goal / ownership

**Korgis** owns the local Qwen Image 2.1 Turbo GGUF Q4_K_M model, artifact downloads/checksums, resident `sd-server`, effective sampler, request admission, runtime identity, resource evidence and `/v1/images/generations`.

**Experiments** owns prompt/dataset selection, repeated sampling, output persistence, scoring, blind review, statistical comparisons and dashboards. Experiments must **not** directly spawn sd-server or duplicate model-download logic.

## Gate E0: only after Korgis proof

- Wait for Korgis K0-K4 (reconciled GGUF baseline, pinned Turbo bundle, exact 8-step sigma sampling, public API and first representative Mac success).
- Capture the exact Korgis code SHA/runtime identity, artifact revisions/hash and effective configuration from a real 1024x1024 generation. Do not present synthetic or 512px smoke as evidence of 1K quality.
- Re-check `dev` vs `main` divergence in both repos before implementation. Do not mass-replace branches.

## E1: add model mapping (small independent PR)

Add `qwen-image-2.1-turbo-gguf-q4km` to `experiments/image-generation-benchmark/models.yaml`:
- `model_id: qwen-image-2.1-turbo-gguf-q4km`, runtime `korgis-image-local`;
- type `text -> image`, no editing claim;
- 1024x1024, PNG, 8 steps, CFG 1, Euler; Korgis is authoritative for Turbo sigmas;
- separate `benchmark_mapping` identity `family=qwen-image-2.1-turbo`, `runtime=stable-diffusion.cpp`, `quantization=Q4_K_M`, checkpoint/revision/runtime config digest where available;
- explicit preflight: available in `/v1/models` and compatible with the inspected `/v1/runtime/identity`. Never silently use standard Qwen 2.1.

Current `KorgisImageProvider` in `src/imagegen_bench/providers/korgis_image.py` is reusable. Do not invent a second inference transport.

## E2: make sampling and persistence evidence-grade

At present the runner's `outputs_per_prompt` is not iterated and the profile seed is saved but not forwarded to actual provider generation. Fix `src/imagegen_bench/planning.py` and `runner.py` to:
1. expand `model x prompt x repetition` deterministically;
2. pass seed to local Korgis when supported; record `seed_requested`, `seed_effective` or `unsupported`, not pretend equivalent seeds across cloud providers;
3. give each sample a unique id/artifact, with incremental evidence writes, resume and no duplicate rows on restart;
4. write a manifest at run creation and store resolved configuration, backend/quantization/SDK/model revision, hardware and timing/cost provenance;
5. carry Korgis effective Turbo schedule/metadata through unmodified and show it in UI.

Do not collapse *generated successfully* into *good image*. Quality evaluators are separate from valid media generation.

## E3: controlled acceptance

- Fake-provider deterministic unit and contract tests first.
- One real Qwen Turbo seed-42 1024x1024 image through Korgis; verify PNG, artifact checksum, identity and sigma metadata.
- Then 4-prompt smoke alongside **separately validated** GPT Image and Nano Banana arms; identical semantic prompt/target aspect; mark native-vs-provider differences.
- Finally 20-prompt suite and repeated runs only after judging/cost gates.

The existing `smoke` profile downscales **standard** Qwen GGUF to 512px; do not copy that override into the 1K quality comparison. If a 512px readiness profile is needed, label it separately.

## E4: authoritative scoring and UI (parallel after schema agreement)

Reuse existing 20 prompts and React gallery; add evidence-linked OCR and prompt-constraint evaluators, versioned results, multi-sample gallery, blinded reviewer IDs, paired human preferences, failures, latency distributions and per-capability breakdown. Public benchmarks can be introduced with dataset revision/license pinning. No opaque overall winner.

## E5: cloud routing through Korgis (separate cross-repo workstream)

The original requirement is that inference be managed by Korgis. Today the benchmark calls GPT Image and Gemini through its own cloud adapters. After local Turbo is proven, decide a narrow Korgis **explicit remote image-provider gateway** contract with credentials/outbound opt-in, cost/rate-limit handling, no resident-local fiction and no automatic local->cloud fallback. Then switch Experiments' OpenAI/Gemini arms to that gateway. This is **not** a precondition for E1's local-model smoke.

## Dependency / PR order

`Korgis K0 -> K1 || K2 -> K3 -> K4 -> Experiments E1 -> E2 -> E3`.
`E4` can proceed with fixtures alongside Korgis; `E5` is a separately reviewed boundary.

Acceptance means a user can select the Turbo arm, invoke only Korgis for local inference, inspect actual output images and reconstruct every run from immutable artifacts and recorded effective settings. No model run is claimed by this plan.
