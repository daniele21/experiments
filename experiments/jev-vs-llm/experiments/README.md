# Experiment catalogue

The Jev vs LLM suite is one repository experiment composed of five controlled sub-experiments. Each folder documents the hypothesis and interpretation; implementation remains shared under `src/jev_bench/` so providers, timing, metrics and reporting stay identical across experiments.

| ID | Experiment | What it isolates |
|---|---|---|
| [01](01-routing/) | Routing / classification | Bounded categorical decision quality and latency |
| [02](02-calibration/) | Calibration / abstention | Whether uncertainty is operationally useful |
| [03](03-parallel-scaling/) | Parallel decision scaling | Cost of adding many independent decisions to one state |
| [04](04-deterministic-workflow/) | Deterministic business workflow | Fuzzy AI judgments + deterministic policy code |
| [05](05-hybrid-agent/) | Hybrid agent decision layer | Decision-model routing vs LLM-centric agent design |

All numeric results are produced by the common runner and rendered into the same HTML dashboard. This is intentional: experiment-specific code should not silently change timing or evaluation behavior.
