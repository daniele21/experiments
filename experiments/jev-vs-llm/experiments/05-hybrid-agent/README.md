# 05 — Hybrid agent decision layer

## Question

Can a decision model handle routing, guardrails and escalation while leaving language generation to an LLM?

## Current stage

The implemented core evaluates the **decision layer** of a support workflow:

- primary intent;
- urgency;
- explicit human request;
- anger / hostility;
- deterministic routing to answer, refund, cancellation, priority support or handoff.

## Comparison

- Jev typed decision layer;
- decomposed LLM decision layer;
- monolithic LLM final-routing baseline.

## Next stage

Add the generation step after routing so the complete architecture becomes:

```text
request
   ↓
decision layer
   ↓
deterministic action / tool policy
   ↓
LLM generation only when language generation is required
```

The expanded evaluation will then measure:

- decision accuracy;
- final task success;
- total end-to-end latency;
- number of LLM calls;
- tokens per task;
- failure / escalation rate.

This is the experiment that tests Jev as an architectural complement to an LLM rather than only as a direct classifier competitor.
