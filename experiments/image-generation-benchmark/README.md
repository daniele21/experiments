# Image Generation Benchmark

Reproducible visual comparison harness for image-generation and image-editing models.

## Current status

Foundation implemented:

- versioned 20-prompt core suite;
- 5 text-rendering prompts;
- 5 compositional prompt-adherence prompts;
- 5 photorealism prompts;
- 5 design/illustration prompts;
- machine-readable expectations and negative constraints;
- deterministic blind A/B assignment;
- OCR-result text metrics;
- smoke/pilot/budget/robust profiles;
- dedicated unit CI.

The first real-model vertical slice compares GPT image and Gemini image on text rendering and
compositionality. Two Qwen-Image-2.1 local arms are available through Korgis: MFlux Q8 and
stable-diffusion.cpp GGUF Q4_K_M. Image editing remains a separate follow-up slice.

## Development

```bash
cd experiments/image-generation-benchmark
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

Provider adapters must preserve the exact prompt, persist generated images through
`benchmark-core` artifact primitives and keep automatic evidence separate from blind human
preference. Provider/runtime metadata is persisted in `evidence.csv`. The React dashboard reads
the run filesystem dynamically, surfaces runtime/backend/quantization provenance in the identified
comparison and hides identity in blind review.

See `IMPLEMENTATION_PLAN.md` for the full workstream.

## Dry-run the first comparison

Resolve the exact model/prompt matrix without making provider calls:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image \
  --profile smoke \
  --output-dir results \
  --dry-run
```

Remove `--dry-run` only after `OPENAI_API_KEY` and `GEMINI_API_KEY` are configured.
The runner writes one run directory containing the manifest, incremental evidence CSV and
content-addressed generated artifacts.

## Explore runs in the React dashboard

The UI is a dynamic React/Vite application. It does not generate per-run HTML files.

```bash
cd ui
npm install
npm run dev
```

By default it reads `../results` and opens on `http://127.0.0.1:5173`.

To point it at another result root:

```bash
IMAGEGEN_RESULTS_ROOT=/absolute/path/to/results npm run dev
```

The dashboard:
- discovers new run directories automatically and refreshes every few seconds;
- compares every selected model side by side per prompt;
- filters by category and model;
- shows latency, validity and provider/runtime/backend/quantization provenance;
- exposes a blind-review tab with every unique model pair for each prompt;
- stores in-progress blind votes locally in the browser and exports them as JSON.

The browser never needs a regenerated `report.html` or `blind_review.html`.


## Add the local Qwen Image 2.1 arm through Korgis

Korgis owns local model download, residency and inference. Start the
`qwen-image-2.1-mflux-q8` runtime in Korgis, then point the benchmark at its local API:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local \
  --profile smoke \
  --output-dir results \
  --dry-run
```

Remove `--dry-run` only after Korgis is resident and the API-provider credentials needed for
the other selected arms are configured. The Qwen arm is recorded as `provider_id=korgis-image`;
it is not mislabeled as an OpenAI provider. The local arm resolves to the MFlux Q8 checkpoint and records `runtime=mflux` plus
`quantization=Q8` in its benchmark mapping. This is a quantized Apple/MLX-oriented profile,
but benchmark reports must not infer real-device memory fit or performance until those values
are measured on representative hardware.


### Add the GGUF Q4_K_M local arm

Keep the MFlux Q8 arm as a separate comparison. The GGUF arm resolves through Korgis to
`qwen-image-2.1-gguf-q4km` and stable-diffusion.cpp:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-local,qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results \
  --dry-run
```

For the full four-arm comparison:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local,qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results
```

The GGUF arm keeps 1024×1024, 20 steps, CFG 6.0 and Euler as its quality-oriented model
configuration, but the `smoke` profile overrides only this arm to **512×512** to reduce peak
memory during local hardware validation. The `budget` profile remains at 1024×1024. The MFlux
arm keeps its own 40-step Q8 configuration.

Profile overrides are persisted as the effective generation configuration in the run manifest and
evidence, so a 512×512 smoke result cannot be mistaken for a 1K quality comparison. The React UI
shows `stable_diffusion_cpp_image`, `Q4_K_M`, and Korgis runtime provenance.


## Qwen Image 2.1 Turbo via Korgis (integration candidate)

Korgis owns the local `qwen-image-2.1-turbo-gguf-q4km` model, three pinned
artifacts, exact eight-step sigma preset, resident `sd-server` and local
`/v1/images/generations` API. Experiments must never launch `sd-server` itself.
This arm requires Korgis [integration PR #259](https://github.com/daniele21/korgis/pull/259)
and a resident compatible native backend. Real device-quality evidence is pending.

```bash
export KORGIS_BASE_URL=http://127.0.0.1:1235
uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-turbo-gguf-q4km \
  --profile smoke \
  --output-dir results \
  --dry-run
```

To run inference, remove `--dry-run` once the model is resident in Korgis.
The Turbo smoke keeps 1024×1024 resolution and does **not** inherit the 512×512
hardware smoke override for standard Qwen GGUF.

The `robust` profile runs all 20 prompts with 3 independent outputs each
(60 local images for a one-model run). Each Korgis request receives an explicit
sample seed (profile seed + zero-based sample index). The evidence CSV records
the requested seed and, if reported by Korgis, the effective seed. API models
that do not expose seed control remain marked as having no requested/effective
seed; seeds across providers are not claimed equivalent. The run manifest is
written before inference and images use unique per-sample IDs. Resume/dedup
across interrupted runs is **not yet implemented**, so each CLI invocation is
a new immutable run; do not portray this as resumable.

## First local Turbo benchmark on Apple Silicon

Use `pilot` for an initial broad coverage check before the `robust` run.
It deterministically samples one existing prompt from each category:
text rendering, compositional adherence, photorealism and design. It makes
**4 images for one model** at 1024×1024, 8 Turbo steps, CFG 1, seed 42.

```bash
export KORGIS_BASE_URL=http://127.0.0.1:1235
uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-turbo-gguf-q4km \
  --profile pilot --output-dir results --dry-run

# Run only after Korgis itself responds to /v1/models:
uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-turbo-gguf-q4km \
  --profile pilot --output-dir results
```

The Mac benchmark runner itself is source-owned by Experiments at
`scripts/run_mac_pilot.sh`. The central self-hosted Action in
`daniele21/local-runner-infra` only checks out the pinned source and calls
that script. Korgis remains solely the inference/model-serving provider. Do not treat
the earlier native `sd-server` smoke as evidence that Korgis' public endpoint
and Experiments' transport work end to end: that path needs its own test.
`pilot` and `smoke` are **not** statistically solid quality comparisons.
The profile `robust` generates 60 images/model and currently has no cross-run
resume or deduplication; avoid launching it automatically on CI until local
pilot validation and human review are complete. Preserve the full run directory
(`manifest.json`, `evidence.csv`, artifacts) for downstream gallery/scoring.

## Local Image-to-Image in the Playground (draft PR #132)

The existing Playground supports both `Text to Image` and a **local-only**
`Image to Image` mode. It requires the [Korgis image-edit PR #260](https://github.com/daniele21/korgis/pull/260)
running with `--image-editing-enabled`, its pinned Qwen3-VL projector present
and checked, and sufficient Mac memory headroom. The feature is deliberately
limited to Qwen Image 2.1 Turbo GGUF; the edit toggle stays disabled for other
models or when the live Korgis `/v1/models` response does not confirm
`image_editing_enabled: true`.

Start Korgis in one terminal (from its edit branch):

```bash
cd ~/Projects/experiments/korgis
git fetch origin
git switch feat/qwen-image-21-turbo-edit-foundation-20261108
git pull --ff-only

uv run --frozen local-llm serve \
  --model qwen-image-2.1-turbo-gguf-q4km \
  --image-editing-enabled \
  --host 127.0.0.1 --port 1235 \
  --sd-server-bin "$HOME/.local-llm/tools/sdcpp-b43af40461cc64c89cac3b621019f8914f50dd9c/build/bin/sd-server" \
  --no-download
```

Then start Experiments from its UI feature branch:

```bash
cd ~/Projects/experiments
git fetch origin
git switch feat/imagegen-playground-image-edit-20261109
git pull --ff-only
cd experiments/image-generation-benchmark/ui
npm ci
KORGIS_BASE_URL=http://127.0.0.1:1235 npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`, choose **Qwen Image 2.1 Turbo**, refresh
engines if you started Korgis later, select **Image to Image**, upload one
PNG, write an edit instruction, choose output size and generate. Results
show original/edited comparison and downloadable PNG. Only the generated
PNG and the source image SHA-256 are persisted by Experiments, in
`playground-results/`; your original upload stays in browser memory
until you leave the page.

First release limits: one original PNG (max 8 MiB, up to 24 megapixels),
one output and 8 Turbo steps. The browser reads source dimensions first and,
when the image is over 1 megapixel or 2048 px on either side, fits it into
1 megapixel without cropping, without upscaling and on a 32px grid. It uses
high-quality canvas interpolation and encodes a new PNG locally. The image
sent to Qwen and used in the Before/After view is this prepared input; the
original file is retained only in the browser for the upload preview.
A versioned `fit-1mp-grid32-canvas-high-v1` resize policy and the
client-reported original dimensions are stored alongside the SHA-256 of the
actual prepared PNG. Dimension selection is deterministic; exact resampled
pixel bytes may vary across browser engines and OS versions. Official
reproducible benchmarks should use a pinned server-side resampler and retain
the prepared input artifact.

Output resolution defaults to **Match source proportions**, using the
prepared image's dimensions rounded to multiples of 32. Users may select
512/768/1024 presets; every output stays within 1MP. Infographics with small
text can lose sharpness when reduced, so the UI displays the before/after
dimensions and the actual model-input preview. No masks,
multi-reference, remote media URL or cloud editing. Only the loopback
Korgis server is contacted by the same-origin Node/Vite proxy.
The host RAM protection remains owned by Korgis; if it refuses startup,
release memory instead of bypassing the admission guard. The 10 GiB
effective editing resident estimate is **provisional** (roughly 15.5 GiB
reclaimable Mac memory required at startup).

To verify UI behavior without loading Qwen:

```bash
cd experiments/image-generation-benchmark/ui
npm test
npm run build
```

**Qwen 2.1 noise replay guard:** image editing defaults to a blank seed
while text-to-image retains a fixed 42 seed for comparative tests. When the
editing seed is blank, Korgis chooses a new random seed for the request and
records the effective seed in the output metadata. Reusing the same RNG/seed
and latent shape that generated the input reference can cause unexpectedly
oversharpened, contrasty and noisy Qwen 2.1 edits. This was reproduced in
[stable-diffusion.cpp issue #2131](https://github.com/leejet/stable-diffusion.cpp/issues/2131)
and [ComfyUI issue #16607](https://github.com/Comfy-Org/ComfyUI/issues/16607).
To troubleshoot, repeat the same input and prompt with seed 43 or a blank seed
instead of 42. The mechanism depends on matching initial noise, not the number
42 specifically, and it is not proof that all visual quality problems share
this cause. Avoid changing CFG or the Turbo eight-step sigma schedule as an
unvalidated sharpening fix.

A successful UI build and mocked proxy test **do not prove image editing
quality or memory safety on the Mac**. Compare before/after manually in a
real native E2E test before merging these draft PRs.

## Playground — prompt to image (UI)

The **Playground** tab is the default landing screen of the existing Vite
dashboard. It supports a single prompt, selecting any image-generation
engine from `models.yaml`, generating one real image, preview and download.
The engine selector groups local Korgis models separately from paid cloud
APIs. The generation defaults (resolution, steps and guidance) come from
the selected model configuration; an optional seed is forwarded only to
the local provider. While generating, a loading state and elapsed time
are shown. No placeholder image is passed off as a generated result.

1. Start Korgis separately for the specific local model you intend to try,
   or configure the chosen cloud API key as a server-side environment
   variable. The UI never receives credentials.
2. Launch the dashboard, binding the Vite backend only on loopback:

```bash
cd experiments/image-generation-benchmark
export KORGIS_BASE_URL=http://127.0.0.1:1235   # local models only
cd ui
npm install
npm run dev
# Open http://127.0.0.1:5173 and select Playground.
```

3. Select `qwen-image-2.1-turbo-gguf-q4km`, edit the prompt, optionally
   change the seed, then click **Generate image**. A single output is
   generated via the existing Experiments Python provider factory, which
   calls Korgis' `/v1/images/generations` on loopback. The preview displays
   only the resulting image, never a fabricated image.

The Vite server handles `GET /api/playground/models`,
`POST /api/playground/generate`, and
`GET /api/playground/image?id=...` with a local, single-flight Python
process, input validation and a same-origin guard. Each result is stored
under `experiments/image-generation-benchmark/playground-results/<id>/`
with the image and a JSON manifest documenting prompt, engine,
parameters, latency and SHA-256. It is deliberately **not** a benchmark
run; it does not appear in the scored comparison list.

Cloud models appear only when their corresponding server-side
`OPENAI_API_KEY` or `GEMINI_API_KEY` is configured; using them may incur
charges. The UI shows a warning before generation but does not silently
make provider calls. Model availability reflects configuration only, not
an active health check. If Korgis is not running, the generation reports
an error; the browser does not start models or download weights.

**Security/deployment:** use the local Vite dev or preview server only
and do not publish it to the internet. The prototype does not implement
remote authentication, multi-user isolation, cancellation or billing
controls. It is a developer tool to try one prompt at a time.

### Local Mac residency and swap telemetry

The Experiments-owned `scripts/run_mac_pilot.sh` now runs a **read-only
admission preflight** against the actual Korgis host-memory guard before any
local generation. It saves `admission-probe.json` with the resident estimate,
measured reclaimable RAM, swap already in use and the admission decision.
A rejection prevents the pilot from loading the model.

During the bounded pilot, `scripts/mac_resource_probe.py` periodically
samples `sd-server` process RSS, macOS `vm_stat` free/inactive/speculative
pages, `Swapins`/`Swapouts` cumulative pages and `vm.swapusage` used bytes.
The raw `mac_resource_samples.jsonl` and derived
`summary.json → mac_resource_telemetry` capture peak native RSS, minimum
reclaimable RAM, swap-use changes and paging-in/out deltas. Readings that are
missing stay `null`. **Swap already used never increases RAM available**,
and process RSS is not equivalent to total Metal or unified-memory use.

These diagnostics measure the specific Mac run; they must not be treated
as model-agnostic memory requirements. The first native proof alone is not
a statistically valid working-set calibration. Do not turn off Korgis'
default memory guard or blindly decrease resource estimates if admission
fails.
