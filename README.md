# Experiments

A collection of heterogeneous, reproducible experiments. Each experiment lives in its own folder under `experiments/` and documents its hypothesis, setup, methodology, metrics, results, and conclusions.

## Experiments

| Experiment | Status | Goal |
|---|---|---|
| [`jev-vs-llm`](experiments/jev-vs-llm/) | In progress | Compare System One decision models and LLMs on accuracy, calibration, latency, scaling, and end-to-end workflows. |
| [`model-capability-benchmark`](experiments/model-capability-benchmark/) | Planned | Compare local and API models across reusable task/dataset suites on quality, validity, latency, token usage, cost, and local runtime characteristics. |
| [`vlm-capability-benchmark`](experiments/vlm-capability-benchmark/) | Planned | Compare local/open and API vision-language models on document, chart, visual reasoning, grounding, and UI-understanding tasks. |
| [`image-generation-benchmark`](experiments/image-generation-benchmark/) | Planned | Compare image-generation/editing models with reproducible prompt suites, objective checks where meaningful, blind human evaluation, and visual side-by-side reports. |
| [`redactguard-local-anonymization`](experiments/redactguard-local-anonymization/) | Initial implementation | Compare local Korgis models on RedactGuard PII recall, leakage, over-redaction, robustness, and latency. |

## Multimodal roadmap

The VLM and image-generation tracks share a small multimodal extension of `benchmark-core` and are designed to be implemented in parallel after that foundation is stable.

See [`experiments/MULTIMODAL_PARALLEL_PLAN.md`](experiments/MULTIMODAL_PARALLEL_PLAN.md).
