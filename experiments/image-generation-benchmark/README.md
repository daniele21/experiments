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
- smoke/budget profiles;
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

The GGUF arm uses 1024×1024, 20 steps, CFG 6.0 and Euler sampling, while the MFlux arm keeps
its own 40-step Q8 configuration. These are recorded as effective generation configurations
rather than being forced into artificial parameter parity. The React UI shows
`stable_diffusion_cpp_image` and `Q4_K_M` from Korgis runtime provenance.
