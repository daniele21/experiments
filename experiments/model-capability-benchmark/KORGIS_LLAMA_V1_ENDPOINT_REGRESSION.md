# Korgis llama.cpp v0.3 ↔ v1 — external endpoint regression

Status: **protocol prepared; no controlled paired endpoint run has passed**.
Owner: `daniele21/experiments` / `model-capability-benchmark` (MCB) external evaluation.
Candidate Korgis source SHA at initial planning: `bbac85ebf2a9be5aa98778e9a9b8de9dcb4afcf6`.
Release reference: [Korgis LC7 contract](https://github.com/daniele21/korgis/blob/dev/docs/workstreams/llama-cpp-v1-integration.md).

## Boundary

Korgis owns its runtime, model registry, native binary selection, host memory
admission, HTTP/streaming, lifecycle, process cleanup and target-Mac safety
evidence (HE-2, RES-2, RRG-5). **Experiments** owns independently exercised
*externally served* endpoint workloads, immutable evidence, paired quality/
latency analysis and regression classification. Never copy MCB's evaluators
into Korgis or change Korgis memory admission to obtain benchmark results.

The existing MCB registry already defines the `korgis` OpenAI-compatible
provider, `korgis-local` runtime and `qwen3.5-0.8b-q4km` model. Reuse the
versioned MCB `model-bench` runner, its immutable `run_manifest.json`
and comparison/reporting instead of creating another benchmark engine.

## Prerequisites: **hard STOP** before inference

1. Confirm exact, fresh Korgis candidate/base SHA, MCB source SHA, source
   model artifact's SHA-256, source revision, quantization, exact native
   llama.cpp tag/commit/binary SHA-256, backend flags, context, sampling,
   GPU layers, thread count and loopback endpoint configuration. Two arms
   must use the **same artifact bytes**, not just the same displayed name.
2. Run Korgis' read-only **canonical host admission** for the intended
   footprint, including OS reserve and current measured pressure.
   Verify exclusive ownership of the intended listener and that no other
   llama-server process is present. If admission rejects, **stop**; a
   workflow/diagnostic success with `ready=false` is not permission to run.
3. Never treat **swap used** as additional free RAM; do not lower Korgis
   safety headroom or kill other applications/processes to make the trial
   run. No silent model downloads or installations. Separate revalidated
   hardware windows are required if memory pressure changes.
4. Do not run both arms concurrently on a 32-GiB shared Mac. Use bounded,
   owned, sequential lifecycles with verified close/unload/port cleanup,
   and keep exact Korgis/MCB SHA unchanged between arms.
5. Korgis' 2026-11-15 read-only [Mac preflight #43770979460](https://github.com/daniele21/local-runner-infra/actions/runs/43770979460)
   observed `ready=false`: 7,550,943,232 reclaimable-estimate bytes
   versus 9,776,843,072 required for the detected 4B candidate,
   with 5,614,012,989 bytes swap-used. A cached 4B hash
   `00fe7986...` is **not** the registry's different LM Studio
   artifact. This observation is a **blocker**, not an executed run;
   refresh the real host observations and exact artifact identity before
   attempting either arm.

## Controlled paired workflow (no implicit execution)

Run from `experiments/model-capability-benchmark` on a properly admitted
Mac with Korgis already running at the **explicit** tagged binary for the
current arm. Do not embed Korgis into this repository or upload local models.

Define `ARM` as `v03` or `v10`, and manually verify that the
externally started Korgis runtime identity/health shows the correct
native engine before proceeding. Use a trusted loopback-only endpoint:

```bash
export KORGIS_BASE_URL=http://127.0.0.1:1235/v1
export MCB_RESOURCE_TELEMETRY=1
export MCB_RESOURCE_SAMPLE_INTERVAL_MS=250
export ARM=v03  # change to v10 only for the separate v1 run

uv run --frozen model-bench validate-config --models qwen3.5-0.8b-q4km
uv run --frozen model-bench run \
  --models qwen3.5-0.8b-q4km \
  --capabilities structured-output \
  --profile smoke \
  --run-group "korgis-llama-${ARM}-smoke" \
  --output-dir "results/scratch/korgis-llama-${ARM}-smoke"

# Preserve separate immutable run IDs for every controlled full arm.
uv run --frozen model-bench run \
  --models qwen3.5-0.8b-q4km \
  --capabilities structured-output,qa-abstention \
  --profile core \
  --run-group "korgis-llama-${ARM}-core"
```

First run only a smoke arm; proceed to core only if both engines are
valid, host admission and provenance remain safe, and teardown is
verified. Capture the distinct core run IDs from MCB's immutable
`results/runs/<run-id>` output. Use `model-bench report --run-dir
results/runs/<run-id>` on each arm, and `model-bench project --rebuild
--export-dashboard` to inspect cross-run history. **Do not**
consolidate v0.3 and v1 into one run: that would mix distinct engine
identities and falsely collapse an independent runtime variable.

## Evidence required for a release-quality regression decision

- The **same** dataset revision, cases/checksums, task parameters,
  generation settings, prompts and sample pairing; a warmup procedure,
  repetitions, order of execution, host pressure/swap counters and
  resulting model outputs/quality evaluation must be recorded under
  their respective private immutable runs.
- Per-arm Korgis version/source SHA, native binary digest, verified model
  digest and runtime fingerprint. MCB's execution identity must record
  the backend revision; if an arm cannot be attributed, mark it **invalid**.
- Compare paired quality, structured validity, error/timeout rates and
  observed HTTP latency with sample counts and variability. Do not
  present 3-run descriptive medians as performance superiority evidence.
- **TTFT, prefill and native decode throughput are not established by
  MCB's current generic completion-latency run or by counting SSE chunks.**
  They require a separate *externally served* controlled streaming
  measurement/telemetry extension in Experiments with explicit event
  semantics, warmup, token accounting and intervals. Until then each
  metric is **unavailable**, not zero or inferred.
- RSS telemetry is sampled process memory, **not** complete Metal/unified
  memory. Native peak, reclamation, thermal and pressure-safe ownership
  remain Korgis' separate physical-Mac acceptance gates.

## Acceptance / disposition

A comparison is **COMPLETE** only after both arms execute as external
Korgis endpoints with matched identity and workload, immutable evidence,
reviewable paired metrics and a documented regression/no-regression
classification. An invalid/missing run, unmatched GGUF, disallowed
resource pressure, or missing required throughput measurement leaves
the applicable comparison gate **PENDING**. Never mark a `dev -> main`
release safe based on this protocol alone.

Related: [MCB HOW_TO_USE](HOW_TO_USE.md),
[MCB README](README.md), `run_manifest.json` and `models.yaml`.
