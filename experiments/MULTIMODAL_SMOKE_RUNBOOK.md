# Multimodal Smoke Runbook

This runbook covers the first controlled real-model smoke runs for:

1. image generation: GPT Image vs Gemini Image, with an optional local Qwen-Image-2.1 arm through Korgis;
2. VLM understanding: Qwen3-VL-4B-Instruct on controlled UI grounding.

The smoke runs are intentionally small. They validate the complete path from configuration to
provider inference, artifact persistence, evaluation and dynamic React exploration before broader suites
are executed.

## 1. Common rules

- Run `--dry-run` first.
- Do not add provider credentials to YAML, source files or committed `.env` files.
- Generated `results/<run-id>/` directories are gitignored.
- Preserve the run manifest, evidence CSV and artifacts together.
- Full/budget suites must not be substituted for smoke runs until the smoke is inspectable.
- Paid image API calls are never part of normal PR CI.

## 2. Image generation smoke

### Scope

The `smoke` profile selects:

- 2 text-rendering prompts;
- 2 compositional prompts;
- 1 output per prompt;
- `openai-sunburst`;
- `gemini-pro-image`.

The baseline paid smoke is 4 prompts × 2 models = 8 generated images.

When local Korgis image runtimes are available, `qwen-image-2.1-local` adds MFlux Q8 and
`qwen-image-2.1-local-gguf-q4km` adds stable-diffusion.cpp GGUF Q4_K_M. The three-arm smoke
with one local arm is 12 images; the four-arm smoke with both local runtimes is 16 images.
Keep local arms separate from the paid GitHub smoke workflow because they require resident
Korgis runtimes.

### Local dry-run

```bash
cd experiments/image-generation-benchmark
uv sync --extra dev

uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image \
  --profile smoke \
  --output-dir results \
  --dry-run
```

Inspect the resolved models and prompt IDs before continuing.

### Start the local GGUF Q4_K_M runtime

From the Korgis repository, point Korgis at a working stable-diffusion.cpp `sd-server`,
download/verify the complete three-artifact bundle, and start the public Korgis API:

```bash
uv sync --frozen --extra dev

export LOCAL_LLM_SD_SERVER_BIN="/absolute/path/to/sd-server"

uv run --frozen local-llm download qwen-image-2.1-gguf-q4km
uv run --frozen local-llm serve \
  --model qwen-image-2.1-gguf-q4km \
  --enable-admin-api \
  --no-download
```

Korgis expects the bundle root to contain the Q4_K_M diffusion GGUF, Qwen3-VL text encoder
GGUF and Qwen Image 2.1 VAE. The public endpoint remains `http://127.0.0.1:1235`.

Before any paid comparison, validate the benchmark mapping against the local runtime:

```bash
cd experiments/image-generation-benchmark
export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results \
  --dry-run
```

Then run the local-only real smoke:

```bash
uv run python scripts/run_benchmark.py \
  --models qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results
```

For the GPT + Gemini + GGUF comparison dry-run:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results \
  --dry-run
```

For a four-arm dry-run that also includes the MFlux Q8 profile:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local,qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results \
  --dry-run
```

The MFlux arm uses Korgis model `qwen-image-2.1-mflux-q8`. The GGUF arm uses
`qwen-image-2.1-gguf-q4km`, a three-artifact stable-diffusion.cpp bundle with Q4_K_M
denoiser, Qwen3-VL text encoder and Qwen Image 2.1 VAE. Record artifact/runtime provenance
without inferring peak memory or performance from file size.

### Real API smoke

Set credentials in the shell:

```bash
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
```

Then run the paid baseline:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image \
  --profile smoke \
  --output-dir results
```

With the GGUF Korgis runtime already running, execute the three-arm comparison with:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local-gguf-q4km \
  --profile smoke \
  --output-dir results
```

The command returns the output root. Keep the benchmark running or completed, then open the
dynamic React dashboard in another shell:

```bash
cd ui
npm install
npm run dev
```

Inspect:

- the run selector;
- the identified comparison tab;
- runtime/provider/quantization provenance;
- the blind-review tab;
- `evidence.csv`;
- `manifest.json`;
- `artifacts/<model-key>/...`.

The dashboard reads the result filesystem dynamically; no per-run HTML regeneration is required.
Blind votes are kept in browser local storage until exported as JSON.

### GitHub manual smoke

The workflow `Image generation paid smoke` is `workflow_dispatch` only.

Required repository secrets:

- `OPENAI_API_KEY`;
- `GEMINI_API_KEY`.

The workflow requires the dispatch input:

```text
RUN
```

Any other value prevents the paid benchmark step from executing.

The workflow uploads the run directory as a GitHub Actions artifact. It is never triggered by
push or pull request events.

## 3. Qwen3-VL local smoke

The benchmark model key remains `qwen3-vl-4b-instruct`, but local inference is owned by
Korgis. The request model ID sent by the benchmark is the Korgis registry key:

```text
qwen3-vl-4b
```

Korgis resolves that key to its registered MLX VLM artifact
`mlx-community/Qwen3-VL-4B-Instruct-4bit`. The benchmark remains backend-agnostic and only
depends on Korgis' OpenAI-compatible HTTP boundary.

### Start Korgis

From the Korgis repository:

```bash
uv sync --frozen --extra dev --extra vision
uv run --frozen local-llm download qwen3-vl-4b
uv run --frozen local-llm serve \
  --model qwen3-vl-4b \
  --enable-admin-api \
  --no-download
```

The default public endpoint is:

```text
http://127.0.0.1:1235
```

The same benchmark can target another Korgis deployment by changing `KORGIS_BASE_URL`.

### Benchmark dry-run

In a separate shell:

```bash
cd experiments/vlm-capability-benchmark
uv sync --extra dev

export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models qwen3-vl-4b-instruct \
  --profile smoke \
  --output-dir results \
  --dry-run
```

### Real VLM smoke

```bash
uv run python scripts/run_benchmark.py \
  --models qwen3-vl-4b-instruct \
  --profile smoke \
  --output-dir results
```

Generate the visual report:

```bash
uv run python scripts/generate_report.py --run-dir results/<run-id>
```

Inspect:

- `evidence.csv`;
- `manifest.json`;
- `report.html`;
- `inputs/...`.

The report overlays the expected target box and predicted click point and shows:

- click hit;
- target-label match;
- normalized point distance;
- inference latency.

## 4. Smoke acceptance criteria

### Image generation

The first real smoke is accepted when:

1. all selected model/prompt cases produce persisted artifacts or typed provider failures
   (8 cases for GPT/Gemini, 12 with one local Qwen arm, 16 with both local Qwen runtimes);
2. the run manifest records every resolved model ID, runtime/provider identity and generation config;
3. the React comparison view renders every selected provider side by side;
4. the React blind-review view does not expose provider/model identity and covers every unique selected-model pair per prompt;
5. blind votes export as JSON without requiring static HTML generation;
6. failures remain inspectable rather than disappearing from the UI/evidence.

### VLM

The first real smoke is accepted when:

1. both controlled UI cases reach the configured Korgis OpenAI-compatible endpoint;
2. input visual evidence is copied into the run directory with SHA-256 provenance;
3. model output is parsed as `target/x/y` or recorded as a typed invalid result;
4. click hit, target match and point distance are persisted separately;
5. the HTML overlay is visually consistent with the evidence CSV.

## 5. After smoke acceptance

Only after both vertical slices are accepted:

- expand VLM into pinned public document/chart datasets;
- add broader visual reasoning and object grounding;
- run the full image-generation v1 prompt suite;
- add repeated generations for stochastic robustness;
- validate the Qwen-Image-2.1 local arm on representative hardware;
- collect representative Apple Silicon evidence for both MFlux Q8 and GGUF Q4_K_M Qwen-Image-2.1 runtimes;
- add image editing/preservation experiments;
- aggregate blind human votes without collapsing capabilities into a single opaque score.
