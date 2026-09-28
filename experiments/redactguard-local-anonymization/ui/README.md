# RedactBench UI

Minimal React/Vite dashboard for exploring local benchmark results.

The UI does not copy or transform benchmark output. A small Vite middleware reads the
experiment's `../results` directory directly, so completed runs become available without
rebuilding a static dashboard.

It discovers:

- direct runs in `results/<run-id>/`;
- incomplete/interrupted direct runs that only contain per-model JSONL evidence;
- managed suites in both `results/suite/<suite-id>/` and
  `results/suites/<suite-id>/`;
- paired `quality/` and `latency/` outputs when both are present.

Incomplete runs are labelled `partial`. Their provisional metrics are recomputed from
the completed scored JSONL rows, so evidence is still inspectable even when the Python
process stopped before writing `manifest.json` and `metrics.json`.

## Run

Install dependencies once:

```bash
npm --prefix ui install
```

Then launch from the experiment root:

```bash
uv run redact-bench ui
```

or directly:

```bash
npm --prefix ui run dev
```

Open <http://127.0.0.1:5173>.

The run index refreshes every five seconds. Selecting a run loads its current
`manifest.json`, `metrics.json`, optional `failures.json`, and paired latency metrics.

## UI scope

The dashboard intentionally stays read-only. Benchmark execution remains owned by the
Python CLI; the React app only visualizes evidence already written under `results/`.


## Unified overview

The dashboard opens on **All models**, a cross-run comparison assembled dynamically from
the result folders.

For each model the overview selects:

1. the newest completed quality benchmark, when one exists;
2. otherwise, the newest partial JSONL evidence.

The table always exposes the source run, completion status and case count so partial
evidence cannot be mistaken for a completed benchmark. The scatter plot and all-model
comparison therefore allow models produced by separate benchmark invocations to be viewed
together while preserving provenance.

The selected run pages remain available in the sidebar for drill-down.
