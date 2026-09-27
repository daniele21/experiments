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

The first real-model vertical slice will compare GPT image and Gemini image on text
rendering and compositionality. Qwen-Image-2.1 and editing are independent follow-up slices.

## Development

```bash
cd experiments/image-generation-benchmark
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

Provider adapters must preserve the exact prompt, persist generated images through
`benchmark-core` artifact primitives and keep automatic evidence separate from blind human
preference.

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

## Generate visual reports

After a completed run:

```bash
uv run python scripts/generate_report.py --run-dir results/<run-id>
```

This creates:
- `report.html`: identified side-by-side comparison by prompt;
- `blind_review.html`: model-hidden A/B evaluation UI with vote export;
- `blind_key.json`: separate A/B-to-model key for post-review analysis.

Do not share `blind_key.json` with reviewers before voting is complete.


## Add the local Qwen Image 2.1 arm through Korgis

Korgis owns local model download, residency and inference. Start the
`qwen-image-2.1` runtime in Korgis, then point the benchmark at its local API:

```bash
export KORGIS_BASE_URL="http://127.0.0.1:1235"

uv run python scripts/run_benchmark.py \
  --models openai-sunburst,gemini-pro-image,qwen-image-2.1-local \
  --profile smoke \
  --output-dir results \
  --dry-run
```

Remove `--dry-run` only after Korgis is resident and the API-provider credentials needed for
the other selected arms are configured. The Qwen arm is recorded as
`provider_id=korgis-image`; it is not mislabeled as an OpenAI provider.
