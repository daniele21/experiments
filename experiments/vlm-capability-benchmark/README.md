# VLM Capability Benchmark

Reproducible benchmark for vision-language models across document/chart understanding,
visual reasoning and grounding tasks.

## Current status

Foundation implemented:

- controlled UI-grounding fixtures;
- deterministic QA/numeric/grounding evaluators;
- normalized `[0, 1]` coordinate semantics;
- smoke suite/profile;
- dedicated unit CI.

Provider/runtime adapters are intentionally separate from task semantics and will be wired
through `benchmark-core` multimodal contracts.

## Development

```bash
cd experiments/vlm-capability-benchmark
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

The initial controlled dataset is
`datasets/controlled_ui_grounding.yaml`. Public DocVQA/ChartQA-style adapters are the next
dataset slice and must pin source revision/license metadata.

See `IMPLEMENTATION_PLAN.md` for the full workstream.

## Dry-run the UI grounding smoke benchmark

Resolve the exact model/case/prompt configuration without starting a local model or making
an inference call:

```bash
uv run python scripts/run_benchmark.py \
  --models qwen3-vl-4b-instruct \
  --profile smoke \
  --output-dir results \
  --dry-run
```

For a real run, serve the configured model through an OpenAI-compatible endpoint, set
`VLM_BASE_URL`, and remove `--dry-run`.

The controlled UI fixtures remain editable SVG sources in the repository. Local SVG assets
are rasterized to PNG before being sent to the VLM, so the runtime receives a conventional
raster image while the benchmark source remains diff-friendly.

## Generate the visual grounding report

After a completed run:

```bash
uv run python scripts/generate_report.py --run-dir results/<run-id>
```

The generated `report.html` embeds the preserved input evidence and overlays:
- the ground-truth target bounding box;
- the model's predicted click point;
- click-hit, label-match, point-distance and latency evidence.

Input visuals are copied into each run directory with SHA-256 evidence, so a run remains
inspectable even if the source dataset later changes.
