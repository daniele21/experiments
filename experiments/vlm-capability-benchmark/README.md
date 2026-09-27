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
