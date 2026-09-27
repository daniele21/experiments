# Multimodal Smoke Runbook

This runbook covers the first controlled real-model smoke runs for:

1. image generation: GPT Image vs Gemini Image;
2. VLM understanding: Qwen3-VL-4B-Instruct on controlled UI grounding.

The smoke runs are intentionally small. They validate the complete path from configuration to
provider inference, artifact persistence, evaluation and HTML reporting before broader suites
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

That is 4 prompts × 2 models = 8 generated images.

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

### Real API smoke

Set credentials in the shell:

```bash
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
```

Then run:

```bash
uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image \
  --profile smoke \
  --output-dir results
```

The command returns the output root. Identify the created run directory and generate both
reports:

```bash
uv run python scripts/generate_report.py --run-dir results/<run-id>
```

Inspect:

- `evidence.csv`;
- `manifest.json`;
- `report.html`;
- `blind_review.html`;
- `blind_key.json`;
- `artifacts/<model-key>/...`.

Keep `blind_key.json` separate from reviewers until blind voting is complete.

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

The first registered VLM baseline is:

```text
Qwen/Qwen3-VL-4B-Instruct
```

Qwen's model documentation exposes it through a vLLM OpenAI-compatible server. The benchmark
adapter therefore remains generic rather than Qwen-specific.

### Start the local server

Use a dedicated environment suitable for the target GPU:

```bash
pip install vllm
vllm serve "Qwen/Qwen3-VL-4B-Instruct"
```

The default endpoint is:

```text
http://localhost:8000
```

The same benchmark can target a remote OpenAI-compatible deployment by changing
`VLM_BASE_URL`.

### Benchmark dry-run

In a separate shell:

```bash
cd experiments/vlm-capability-benchmark
uv sync --extra dev

export VLM_BASE_URL="http://localhost:8000"

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

1. all 8 model/prompt cases produce persisted artifacts or typed provider failures;
2. the run manifest records both resolved model IDs and generation config;
3. `report.html` renders both providers side by side;
4. `blind_review.html` does not expose provider/model identity;
5. `blind_key.json` contains the reversible A/B mapping;
6. failures remain inspectable rather than disappearing from the report/evidence.

### VLM

The first real smoke is accepted when:

1. both controlled UI cases reach the configured OpenAI-compatible endpoint;
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
- add Qwen-Image-2.1;
- add image editing/preservation experiments;
- aggregate blind human votes without collapsing capabilities into a single opaque score.
