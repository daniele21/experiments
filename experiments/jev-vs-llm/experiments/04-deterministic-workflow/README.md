# 04 — Deterministic business workflow

## Question

Is it better to ask AI for a final business decision, or to use AI only for **fuzzy judgments** and keep policy logic deterministic?

## Smoke workflow

Expense approval decomposes the request into judgments such as:

- receipt readable?;
- expense category?;
- claim description matches receipt?;
- fraud / tampering signal?

Python then applies the explicit business policy and emits one final action:

```text
approve
manager_review
request_receipt
review
```

## Comparison arms

1. **Jev workflow** — typed sub-decisions + Python rules.
2. **LLM workflow** — equivalent structured sub-decisions + the same Python rules.
3. **LLM monolithic** — full policy in one prompt, final action directly from the LLM.

This three-way comparison distinguishes the effect of the model from the effect of decomposing the workflow.

## Primary metrics

- final-action accuracy;
- intermediate decision accuracy;
- valid-output rate;
- p50 / p95 / p99 latency;
- token usage.

Final-action accuracy is the primary metric. Intermediate decisions are diagnostic and do not receive extra weight in the aggregate score.
