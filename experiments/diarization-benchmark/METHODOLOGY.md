# Methodology

## Objective

Measure speaker-diarization quality and device cost for local Apple-Silicon meeting workloads without turning different operating points into a single opaque score.

## Protocol

The initial protocol uses DER with:

- 0 second collar;
- overlapping speech included;
- optimal one-to-one speaker mapping based on accumulated overlap;
- exact reference speaker-time denominator.

Error is decomposed into miss, false alarm and speaker confusion.

JER is reported independently using optimal reference/hypothesis pairing by speaker IoU. Speaker-count accuracy is reported because a low aggregate DER can still hide a product-breaking merge or split.

## Efficiency

For each model x case attempt the benchmark records:

- audio duration;
- audio normalization time;
- model load time;
- inference wall time;
- complete helper wall time;
- inference RTF;
- complete wall RTF;
- peak helper RSS;
- helper CPU seconds.

The Python orchestrator launches the already-built release helper so compilation is outside the measured attempt.

GPU/ANE energy is not claimed yet. macOS power instrumentation generally requires privileged or machine-specific setup, so it should be added only with a representative real-environment protocol rather than inferred from CPU/RSS.

## Dataset design

The first useful suite should be intentionally compact and stratified rather than huge. Include cases that discriminate model behavior:

| Dimension | Suggested bands |
|---|---|
| speakers | 2, 3-4, 5-8 |
| overlap | low, medium, high |
| acoustics | clean, noisy/distant |
| turn style | long turns, short interruptions |
| capture | remote/system-like, room mic |

Keep private recordings outside git. Public benchmark corpora can be referenced by local manifests.

## Tuning rule

Do not tune post-processing on the held-out comparison set. If thresholds or variants are tuned, record the development cases and freeze the chosen configuration before the final run.

LS-EEND is domain-sensitive, so its variant is part of the model configuration and must be visible in run evidence.

## Decision rule

No overall winner field is produced.

For ClosedRoom, a candidate should be assessed on a Pareto view of:

- DER/JER;
- speaker-count reliability;
- overlap and many-speaker slices;
- inference RTF;
- peak RSS;
- product constraints such as max speaker count and runtime compatibility.

A model with slightly worse mean DER can still be the better product backend if it is materially more stable on ClosedRoom's actual meeting distribution.
