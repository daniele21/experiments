# RedactGuard Benchmark Lab

Local React/Vite workspace for presenting benchmark results and exploring their evidence.

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


## Workspace journey

The entry page (`/client/experiments`) is an experiment library organized by dataset.
SPACCC, ASQ-PHI, E3C, synthetic healthcare, realistic documents, challenge and
ambiguous datasets stay separate. Unknown and partial runs remain accessible.
The library does not load document payloads or silently select a benchmark.

1. Choose a dataset, then an execution identified by date, case count and models.
2. **Risultati** presents a same-execution summary, model measurements and gold scope.
   **Stampa report** prints this view without workspace navigation.
3. **Casi & errori** filters and compares documents, then opens the existing masked
   annotation inspector. Missing or unverifiable source text remains unavailable.
4. **Confronto dataset** shows each model's latest eligible measurement per exact
   dataset version. Every cell links to its original execution; scores are never
   averaged across datasets.

Technical diagnostics remain under **Analisi tecnica**. Existing model/document
URLs remain valid, and the selected run is preserved through document navigation.
The workspace supports light/dark/system appearance and responsive layouts.
