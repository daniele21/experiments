# 03 — Parallel decision scaling

## Question

How does end-to-end latency change when the same state requires **more independent decisions**?

## Protocol

One customer-support state is held fixed. The request contains:

```text
1 → 2 → 4 → 8 → 16 → 32
```

independent questions.

Jev receives all questions in one System One request. The LLM workflow receives the same logical questions in one structured request.

## Primary metrics

- latency p50 / p95 / p99 by question count;
- relative latency growth vs one question;
- input/output token usage where exposed;
- request failure rate.

Latency is measured at the client boundary. Provider retries are disabled by default for both SDKs, and the same timeout is used.

## Why it matters

This test isolates one of the central architectural claims behind a decision model: adding independent decisions should not necessarily incur the same sequential decoding cost as generating more structured output autoregressively.

The experiment must be interpreted empirically; the chart is designed to show the actual curve rather than assume its shape.
