# Decision Benchmark Dashboard

The dashboard always displays the latest recorded run for each provider, model,
configuration, dataset and task. Smoke results are excluded from every view.
Failed latest runs remain visible; they never fall back to an older successful run.

The dataset selector offers **Overall** and one view per available dataset.
Overall pools the selected runs (accuracy weighted by evaluated decisions), while
dataset views recompute rankings, KPIs, charts and case details independently.
Models may have different dataset coverage; included datasets and the latest run
timestamp appear in the leaderboard. Thinking mode, model/quantization and recorded
generation parameters distinguish configurations; unknown historical settings are
not inferred from the current registry.

Regenerate data and the standalone report from the experiment directory:

```sh
uv run jev-bench report --input-csv results/raw/local_results.csv --output-html results/local_report.html
```

`npm run dev` serves the interactive dashboard; `npm run build` produces a single
HTML file in `dist/index.html` and updates `../results/local_report.html`.

## Development

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
