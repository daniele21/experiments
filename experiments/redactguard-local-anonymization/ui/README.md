# RedactBench UI

Minimal React/Vite dashboard for exploring local benchmark results.

The UI does not copy or transform benchmark output. A small Vite middleware reads the
experiment's `../results` directory directly, so completed runs become available without
rebuilding a static dashboard.

It discovers:

- direct runs in `results/<run-id>/`;
- managed suites in both `results/suite/<suite-id>/` and
  `results/suites/<suite-id>/`;
- paired `quality/` and `latency/` outputs when both are present.

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
