# Mathematical reasoning v3 — benchmark contract

## Scope

- Dataset key: `math-reasoning-controlled-v3`
- Source: `data/math-reasoning-controlled-v3.yaml` (repository-authored JSON-compatible YAML)
- 72 **new** cases with stable, distinct `math3-*` sample IDs, 12 each in arithmetic, percentages, multi_step, algebra, logic and constraints.
- Difficulty labels: 20 medium, 36 hard, 16 challenge. Labels are **authored and provisional**, not calibrated by humans or empirical model-response curves.
- Expected values: unambiguous finite numerical answers (integer or exact terminating decimal). A response is graded using the existing `final_answer_accuracy` scorer against its final `answer` field; the model's intermediate reasoning is never requested or scored.
- Each case includes `family`, `difficulty`, and `challenge_type`. Prompts specify boundaries, units, and any necessary assumptions.

## Reproducible tiers

| Profile | Selected v3 cases | Selection |
|---|---:|---|
| smoke | 12 | stratified: 2 per family |
| core | 40 | stratified: arithmetic 7, percentages 7, multi_step 7, algebra 7, logic 6, constraints 6 |
| extended | 72 | fixed selection: all cases |

The default `mathematical-reasoning` capability uses v3 as of **suite version 3**. The overall core suite still has **468 cases/model** (154 + 154 + 60 + 60 + 40). V1 and v2 are preserved in `datasets.yaml`, and v2's 40 original cases remain unchanged.

**Do not compare v3 accuracy against historic v2 accuracy as if the items were the same.** Model-vs-model comparisons must use the same version, tier, seed, evaluator, and generation configuration. The dataset file checksum, registry version, run manifest, and selection fingerprint provide auditable lineage.

## Test commands

From `experiments/model-capability-benchmark`:

```bash
uv sync --extra dev
uv run pytest tests/test_dataset_adapters.py tests/test_capability_suite.py tests/test_planning.py
uv run model-bench plan --capabilities mathematical-reasoning --profile core
uv run model-bench plan --capabilities mathematical-reasoning --profile extended
```

For a selected **configured and available** model:

```bash
uv run model-bench estimate --models YOUR_MODEL_KEY --capabilities mathematical-reasoning --profile core --pilot-cases 5
uv run model-bench run --run-group math-v3-core --models YOUR_MODEL_KEY --capabilities mathematical-reasoning --profile core
uv run model-bench run --run-group math-v3-extended --models YOUR_MODEL_KEY --capabilities mathematical-reasoning --profile extended
```

Run each model in an independent immutable run, with matched cases/configuration for paired analyses. Do not treat dataset validation as actual inference validation.

## Limitations and next calibration pass

This is a **harder school-level/numeric reasoning suite**, not a substitute for independently sourced contest-math benchmarks such as AIME. Some strong math-tuned models may saturate it. There has been no blind human review or measured item difficulty calibration yet. Before publishing score claims, independently review every item/solution, estimate per-item discrimination across a representative set of models, and check for contamination.

The shared mathematical-reasoning task currently requests a single structured final answer and applies a 256-token generation cap. Reasoning-native models may need a separately versioned generation/prompt configuration with sufficient output budget; do not silently vary those settings between model comparisons.
