# MCB-2D — Shared Transports and Error Policy

Status: **COMPLETE** — focused transport/provider gate green (18/18) and full Jev characterization suite green (52/52).

MCB-2D is the final extraction slice required to complete MCB-2. It moves reusable
transport mechanics into `benchmark-core` while keeping provider-specific prompts,
wire semantics and decision parsing inside `jev-vs-llm`.

## Shared transport layer

New package:

- `benchmark_core.transports`.

It contains four independent concerns.

### TransportPolicy

`TransportPolicy` owns the two transport-level execution controls shared across providers:

- max retries;
- timeout seconds.

`resolve_transport_policy` resolves those values from environment/config without coupling
the core to a specific provider.

### JsonHttpTransport

The generic JSON HTTP transport owns:

- JSON request encoding;
- JSON response decoding;
- headers;
- GET/POST/DELETE and other HTTP verbs;
- timeout application;
- retry on HTTP 429 and 5xx;
- retry on timeout/URL transport failures;
- authentication HTTP status classification;
- invalid JSON classification.

It does not know anything about Jev, CLM, Korgis, model prompts or benchmark tasks.

### OpenAI-compatible client construction

`create_openai_compatible_client` centralizes only transport/client construction:

- base URL;
- API key;
- timeout;
- max retries.

The function receives the SDK client factory by dependency injection, so benchmark-core
does not depend on the OpenAI Python package.

### Typed transport errors

`TransportError` separates:

- authentication;
- timeout;
- transport;
- invalid response.

`inference_error_from_exception` maps transport exceptions to the generic
`InferenceError` vocabulary introduced in MCB-1.

## Jev integrations

### OpenAIProvider

Uses shared policy resolution and shared OpenAI-compatible client construction.

Prompt, structured-output schema and `Decision` parsing remain Jev-owned.

### MiniCPMProvider

Uses the same client-construction path, preserving its ModelBest endpoint, API-key
requirements and decision parser.

### KorgisProvider

Uses shared OpenAI-compatible construction while preserving the explicit Korgis rule of
zero SDK retries for local benchmark inference.

### KorgisController

Control-plane JSON calls now use `JsonHttpTransport`.

Korgis lifecycle semantics remain outside benchmark-core.

### CLMProvider

The `/v1/systemone` HTTP boundary now uses `JsonHttpTransport`.

CLM still owns:

- its endpoint path;
- bearer-token selection;
- payload shape;
- server latency header interpretation;
- answer/probability validation;
- CLM-specific `QuestionSpec` wire representation.

## Architectural boundary

```text
benchmark-core
  TransportPolicy
  JsonHttpTransport
  TransportError
  OpenAI-compatible client factory
             |
             v
experiment/provider adapters
  endpoint choice
  auth env names
  payload construction
  prompt/schema
  response semantics
  task-specific parsing
```

This prevents generic infrastructure from acquiring bounded-decision semantics.

## Retry semantics

The generic JSON transport retries only failures that are plausibly transient:

- HTTP 429;
- HTTP >= 500;
- timeout;
- URL/network transport failures.

Authentication failures and invalid JSON are fail-closed and non-retryable.

Provider SDKs can apply the same `TransportPolicy`, but SDK-specific retry behavior
remains delegated to their clients.

## What remains outside MCB-2

Typed model/runtime/provider registry resolution is MCB-3.

Task dispatch/plugins are MCB-4.

Dataset adapters are MCB-5.

The unified matrix runner is MCB-7.

No additional provider-specific transport code should be promoted into benchmark-core
unless it is demonstrably reusable across experiment suites.

## Definition of Done

- [x] generic transport policy exists;
- [x] generic JSON HTTP transport exists;
- [x] typed transport errors exist;
- [x] OpenAI-compatible client construction is shared;
- [x] OpenAI provider uses shared client construction;
- [x] MiniCPM provider uses shared client construction;
- [x] Korgis provider/controller use shared transport primitives;
- [x] CLM provider uses shared JSON transport;
- [x] prompt/parsing semantics remain experiment-owned;
- [x] retry behavior has focused contract tests;
- [x] auth/timeout/invalid-response errors have focused contract tests;
- [x] focused MCB-2D CI passes (18/18);
- [x] previous MCB gates remain green;
- [x] full Jev characterization suite remains green (52/52).
