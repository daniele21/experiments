# 02 — Calibration / abstention

## Question

Does the model expose uncertainty that can be used to decide **when to automate and when to abstain / escalate**?

## Public benchmark

The benchmark mixes:

- BANKING77 in-scope requests;
- conservatively filtered CLINC150 `oos_test` requests;
- one explicit `other` choice.

The full profile uses all available filtered OOS cases and matches them with the same number of BANKING77 examples.

## Two uncertainty signals

The suite keeps these separate:

- **predicted_probability** — estimated probability that the selected class is correct; used for probability calibration metrics;
- **confidence** — provider-native decision confidence; used as an abstention / automation score.

For Jev, the selected-class probability comes from its returned Choice probability distribution. Jev's native confidence is not treated as the same quantity.

For the LLM baseline, both signals are explicitly requested scalars and are therefore self-reported.

## Primary metrics

- ECE on selected-class probability;
- Brier score on selected-class probability;
- reliability diagram;
- accuracy vs coverage as confidence threshold rises;
- in-scope vs OOS accuracy;
- mean confidence by scope.

## Operational interpretation

The key question is not simply "which model is better calibrated?" but:

> At a required accuracy level, what fraction of requests can be automated?

That is what the accuracy-vs-coverage curve is designed to show.
