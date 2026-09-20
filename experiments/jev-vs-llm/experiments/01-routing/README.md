# 01 — Routing / fixed classification

## Question

For a bounded decision with many allowed labels, how do Jev and an LLM compare on **correctness and end-to-end latency**?

## Public benchmark

- Dataset: BANKING77 official test split.
- Decision space: 77 banking intents.
- Jev: one `Choice` over the same labels.
- LLM: strict Structured Output containing only the chosen label, native confidence and selected-class probability.
- Ground truth: upstream test labels.

The LLM is deliberately **not** asked to emit all 77 class probabilities. Jev exposes the distribution natively, while forcing the LLM to generate 77 probabilities token by token would distort the latency comparison.

## Primary metrics

- accuracy;
- macro-F1;
- 95% Wilson interval for accuracy;
- valid-output rate;
- p50 / p95 / p99 latency;
- top confusion pairs.

## Profiles

- `quick`: 154 cases;
- `standard`: 770 cases;
- `full`: all official test cases.

Subset profiles are sampled approximately uniformly across labels with a deterministic seed.

## Read the dashboard

The most useful plots are **Primary outcome accuracy**, **Accuracy vs latency**, **Median request latency**, and **Most frequent confusion pairs**.

A latency advantage is meaningful only if classification quality remains comparable for the intended application.
