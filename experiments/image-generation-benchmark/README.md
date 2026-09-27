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
