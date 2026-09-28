import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const REFRESH_MS = 5000;

function micro(summary) {
  return summary?.micro ?? summary ?? {};
}

function percentValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  const numeric = Number(value);
  return numeric <= 1.000001 ? numeric * 100 : numeric;
}

function formatPercent(value, digits = 1) {
  const normalized = percentValue(value);
  return normalized === null ? "—" : `${normalized.toFixed(digits)}%`;
}

function formatMs(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const numeric = Number(value);
  return numeric >= 1000 ? `${(numeric / 1000).toFixed(2)} s` : `${numeric.toFixed(0)} ms`;
}

function formatDate(value) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function shortDataset(value) {
  if (!value) return "dataset";
  const parts = String(value).split(/[\\/]/).filter(Boolean);
  return parts.at(-1) ?? value;
}

function clamp(value, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}

function contractState(summary, evidence, run) {
  const values = micro(summary);
  if (values.status === "contract_failed" || evidence?.contractStatus === "failed") {
    return "failed";
  }
  if (evidence?.legacy || run?.legacy) return "legacy";
  return "passed";
}

function contractLabel(state) {
  if (state === "failed") return "FAILED";
  if (state === "legacy") return "LEGACY";
  return "PASS";
}

function MetricCard({ label, value, hint, tone = "neutral" }) {
  return (
    <div className={`metric-card metric-card--${tone}`}>
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

function MiniBar({ value, inverse = false }) {
  const percentage = percentValue(value);
  const width = percentage === null ? 0 : clamp(percentage);
  return (
    <div className="mini-bar" aria-hidden="true">
      <span
        className={inverse ? "mini-bar__fill mini-bar__fill--risk" : "mini-bar__fill"}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function StatusBadge({ state }) {
  return (
    <span className={`status-badge status-badge--${state}`}>
      {contractLabel(state)}
    </span>
  );
}

function RunList({ runs, selectedKey, onSelect }) {
  if (!runs.length) {
    return (
      <div className="empty-state compact">
        <strong>No runs yet</strong>
        <span>Run the benchmark and this list will populate automatically.</span>
      </div>
    );
  }

  const uniqueModels = new Set(runs.flatMap((run) => run.models ?? [])).size;

  return (
    <div className="run-list">
      <button
        type="button"
        className={
          selectedKey === "__overview__"
            ? "run-item overview-item active"
            : "run-item overview-item"
        }
        onClick={() => onSelect("__overview__")}
      >
        <div className="run-item__top">
          <strong>All models</strong>
          <span className="pill pill--overview">overview</span>
        </div>
        <span>Unified best available evidence</span>
        <div className="run-item__meta">
          <span>cross-run</span>
          <span>{uniqueModels} model{uniqueModels === 1 ? "" : "s"}</span>
        </div>
      </button>
      <div className="run-list__divider" />

      {runs.map((run, index) => (
        <button
          type="button"
          key={run.key}
          className={selectedKey === run.key ? "run-item active" : "run-item"}
          onClick={() => onSelect(run.key)}
        >
          <div className="run-item__top">
            <strong>{run.suiteId || run.runId}</strong>
            <span className="run-badges">
              {run.legacy ? <span className="pill pill--legacy">legacy</span> : null}
              {run.status === "incomplete" ? (
                <span className="pill pill--partial">partial</span>
              ) : null}
              {index === 0 ? <span className="pill">latest</span> : null}
            </span>
          </div>
          <span>{formatDate(run.createdAt)}</span>
          <div className="run-item__meta">
            <span>{shortDataset(run.dataset)}</span>
            <span>{run.models.length} model{run.models.length === 1 ? "" : "s"}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function QualityLatencyChart({ detail }) {
  const data = useMemo(() => {
    if (!detail) return [];
    return Object.entries(detail.metrics ?? {})
      .map(([model, summary]) => {
        const quality = micro(summary);
        if (quality.quality_available === false) return null;
        const dedicatedLatency = micro(detail.latency?.metrics?.[model]);
        const recall = percentValue(quality.pii_recall);
        const latency =
          dedicatedLatency.latency_p95_ms ??
          dedicatedLatency.p95_ms ??
          quality.latency_p95_ms ??
          null;
        if (recall === null || latency === null) return null;
        return {
          model,
          recall,
          latency: Number(latency),
          legacy: Boolean(detail.evidence?.[model]?.legacy),
        };
      })
      .filter(Boolean);
  }, [detail]);

  if (!data.length) {
    return (
      <div className="chart-empty">
        No valid quality + latency evidence is available for this selection.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 18, right: 20, bottom: 12, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.25} />
        <XAxis
          type="number"
          dataKey="latency"
          name="p95 latency"
          unit=" ms"
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="number"
          dataKey="recall"
          name="Recall"
          unit="%"
          domain={[0, 100]}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          formatter={(value, name) =>
            name === "Recall"
              ? [`${Number(value).toFixed(1)}%`, name]
              : [formatMs(value), "p95 latency"]
          }
          labelFormatter={(_, payload) => {
            const item = payload?.[0]?.payload;
            return item ? `${item.model}${item.legacy ? " · legacy" : ""}` : "";
          }}
        />
        <Scatter name="Models" data={data} fill="var(--accent)" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function PiiChart({ summary }) {
  const values = micro(summary);
  const rows = useMemo(
    () =>
      Object.entries(summary?.by_type ?? {}).map(([type, metrics]) => ({
        type,
        recall: percentValue(metrics.pii_recall) ?? 0,
        precision: percentValue(metrics.precision) ?? 0,
        leakage: percentValue(metrics.leakage_rate) ?? 0,
      })),
    [summary],
  );

  if (values.quality_available === false || !rows.length) {
    return (
      <div className="chart-empty">
        No valid per-PII quality evidence is available for this model.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(280, rows.length * 42)}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 8, right: 12, bottom: 8, left: 16 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.25} />
        <XAxis type="number" domain={[0, 100]} unit="%" tickLine={false} axisLine={false} />
        <YAxis
          type="category"
          dataKey="type"
          width={110}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
        <Legend />
        <Bar dataKey="recall" name="Recall" fill="var(--accent)" radius={[0, 4, 4, 0]} />
        <Bar dataKey="precision" name="Precision" fill="var(--series-2)" radius={[0, 4, 4, 0]} />
        <Bar dataKey="leakage" name="Quality leakage" fill="var(--risk)" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ModelTable({ detail }) {
  const models = detail?.summary?.models ?? [];
  const unified = Boolean(detail?.evidence);

  return (
    <div className="table-scroll">
      <table className="comparison-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Evidence</th>
            <th>Contract</th>
            <th>Evaluated</th>
            <th>Recall</th>
            <th>Quality leak</th>
            <th>System leak</th>
            <th>Precision</th>
            <th>Success</th>
            <th>Trunc.</th>
            <th>Resolution</th>
            <th>p95</th>
            {unified ? <th>Source run</th> : null}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => {
            const summary = micro(detail.metrics?.[model]);
            const latency = micro(detail.latency?.metrics?.[model]);
            const evidence = detail.evidence?.[model];
            const state = contractState(detail.metrics?.[model], evidence, detail.summary);
            const totalCases = summary.cases ?? evidence?.cases ?? "—";
            const evaluatedCases =
              summary.evaluated_cases ?? evidence?.evaluatedCases ?? (summary.quality_available ? totalCases : 0);

            return (
              <tr key={model}>
                <td className="model-name">{model}</td>
                <td className="status-cell">
                  <span
                    className={
                      (evidence?.status ?? detail.summary?.status) === "incomplete"
                        ? "status-badge status-badge--partial"
                        : "status-badge status-badge--complete"
                    }
                  >
                    {(evidence?.status ?? detail.summary?.status) === "incomplete"
                      ? "partial"
                      : "complete"}
                  </span>
                </td>
                <td className="status-cell">
                  <StatusBadge state={state} />
                </td>
                <td>{evaluatedCases}/{totalCases}</td>
                <td>
                  <span>{formatPercent(summary.pii_recall)}</span>
                  <MiniBar value={summary.pii_recall} />
                </td>
                <td>
                  <span>{formatPercent(summary.leakage_rate)}</span>
                  <MiniBar value={summary.leakage_rate} inverse />
                </td>
                <td>
                  <span>{formatPercent(summary.system_leakage_rate ?? summary.leakage_rate)}</span>
                  <MiniBar value={summary.system_leakage_rate ?? summary.leakage_rate} inverse />
                </td>
                <td>{formatPercent(summary.precision)}</td>
                <td>{formatPercent(summary.inference_success_rate ?? summary.valid_output_rate)}</td>
                <td>{formatPercent(summary.truncation_rate)}</td>
                <td>{formatPercent(summary.span_resolution_rate)}</td>
                <td>{formatMs(latency.latency_p95_ms ?? summary.latency_p95_ms)}</td>
                {unified ? (
                  <td className="source-run-cell">
                    <strong>{evidence?.suiteId || evidence?.runId || "—"}</strong>
                    <small>{formatDate(evidence?.createdAt)}</small>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FailureExplorer({ failures }) {
  if (!failures?.length) {
    return (
      <div className="empty-state">
        <strong>No recorded failures</strong>
        <span>This model has no quality or inference failures in this evidence.</span>
      </div>
    );
  }

  return (
    <div className="failure-list">
      {failures.slice(0, 20).map((failure, index) => {
        const qualityAvailable = failure.quality_available !== false;
        return (
          <details key={`${failure.case_id ?? "case"}-${index}`}>
            <summary>
              <span>
                <strong>{failure.case_id ?? "Unknown case"}</strong>
                <small>
                  {qualityAvailable
                    ? `Recall ${formatPercent(failure.pii_recall)} · Quality leakage ${formatPercent(
                        failure.leakage_rate,
                      )}`
                    : `Quality N/A · ${failure.inference_status ?? failure.error_type ?? "inference failure"}`}
                </small>
              </span>
              <span className="failure-counts">
                {qualityAvailable
                  ? `FN ${failure.fn ?? 0} · FP ${failure.fp ?? 0}`
                  : `System FN ${failure.system_fn ?? "—"}`}
              </span>
            </summary>

            <div className="failure-diagnostics">
              <span>
                <strong>System leakage</strong>
                {formatPercent(failure.system_leakage_rate)}
              </span>
              <span>
                <strong>Unresolved items</strong>
                {failure.unresolved_item_count ?? 0}
              </span>
              <span>
                <strong>Status</strong>
                {failure.inference_status ?? "success"}
              </span>
            </div>

            {qualityAvailable ? (
              <div className="failure-body">
                <div>
                  <span className="eyebrow">Missed gold spans</span>
                  {(failure.false_negatives ?? []).length ? (
                    <ul>
                      {failure.false_negatives.slice(0, 12).map((item, itemIndex) => (
                        <li key={itemIndex}>
                          <code>{item.pii_type ?? "PII"}</code> {item.value ?? ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">None</p>
                  )}
                </div>
                <div>
                  <span className="eyebrow">Unmatched resolved predictions</span>
                  {(failure.false_positives ?? []).length ? (
                    <ul>
                      {failure.false_positives.slice(0, 12).map((item, itemIndex) => (
                        <li key={itemIndex}>
                          <code>{item.pii_type ?? "PII"}</code> {item.value ?? ""}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">None</p>
                  )}
                </div>
              </div>
            ) : null}

            {failure.error || failure.error_type ? (
              <p className="error-inline">
                {failure.error_type ? `${failure.error_type}: ` : ""}
                {failure.error ?? ""}
              </p>
            ) : null}
          </details>
        );
      })}
    </div>
  );
}

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selectedKey, setSelectedKey] = useState("__overview__");
  const [detail, setDetail] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadRuns = useCallback(async () => {
    try {
      const response = await fetch("/api/runs", { cache: "no-store" });
      if (!response.ok) throw new Error(`Runs request failed: ${response.status}`);
      const payload = await response.json();
      const nextRuns = payload.runs ?? [];
      setRuns(nextRuns);
      setSelectedKey((current) => {
        if (current === "__overview__") return current;
        if (current && nextRuns.some((run) => run.key === current)) return current;
        return "__overview__";
      });
      setLastRefresh(new Date());
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  useEffect(() => {
    loadRuns();
    const timer = window.setInterval(loadRuns, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedKey) {
      setDetail(null);
      setSelectedModel(null);
      return undefined;
    }

    const controller = new AbortController();
    setLoadingDetail(true);
    const endpoint =
      selectedKey === "__overview__"
        ? "/api/overview"
        : `/api/run?key=${encodeURIComponent(selectedKey)}`;

    fetch(endpoint, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Run request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setDetail(payload);
        setSelectedModel((current) =>
          current && payload.summary.models.includes(current)
            ? current
            : payload.summary.models[0] ?? null,
        );
        setError(null);
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setError(requestError instanceof Error ? requestError.message : String(requestError));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingDetail(false);
      });

    return () => controller.abort();
  }, [selectedKey, lastRefresh]);

  const currentSummary = detail?.metrics?.[selectedModel] ?? null;
  const currentMicro = micro(currentSummary);
  const currentLatency = micro(detail?.latency?.metrics?.[selectedModel]);
  const selectedRun =
    detail?.summary ??
    (selectedKey === "__overview__"
      ? {
          key: "__overview__",
          runId: "Unified overview",
          models: [],
          source: "overview",
          status: "complete",
        }
      : runs.find((run) => run.key === selectedKey));
  const selectedEvidence = detail?.evidence?.[selectedModel] ?? null;
  const failures = detail?.failures?.[selectedModel] ?? [];
  const selectedContractState = contractState(
    currentSummary,
    selectedEvidence,
    selectedRun,
  );
  const selectedPreflight =
    selectedEvidence?.preflight ??
    detail?.preflight?.[selectedModel] ??
    currentSummary?.preflight ??
    null;

  const latencyP95 = currentLatency.latency_p95_ms ?? currentMicro.latency_p95_ms;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <strong>RedactBench</strong>
            <span>Local results explorer</span>
          </div>
        </div>

        <div className="sidebar-heading">
          <span>Runs</span>
          <span className="live-dot">
            <i />
            auto 5s
          </span>
        </div>

        {loadingRuns ? (
          <div className="loading-line">Loading runs…</div>
        ) : (
          <RunList runs={runs} selectedKey={selectedKey} onSelect={setSelectedKey} />
        )}
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <div className="kicker">Benchmark results</div>
            <h1>
              {selectedRun?.source === "overview"
                ? "Unified model overview"
                : selectedRun?.suiteId || selectedRun?.runId || "No run selected"}
            </h1>
            <p>
              {selectedRun?.source === "overview"
                ? "Current contract evidence is preferred; legacy runs remain visible only as diagnostic fallback."
                : selectedRun
                  ? `${shortDataset(selectedRun.dataset)} · ${formatDate(selectedRun.createdAt)}`
                  : "Run a benchmark to populate the dashboard."}
            </p>
          </div>
          <button type="button" className="refresh-button" onClick={loadRuns}>
            Refresh
            <small>{lastRefresh ? lastRefresh.toLocaleTimeString() : ""}</small>
          </button>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        {loadingDetail ? (
          <div className="loading-panel">Loading benchmark data…</div>
        ) : !selectedRun ? (
          <div className="empty-state large">
            <strong>No benchmark results found</strong>
            <span>
              The UI reads completed and partial runs directly from <code>results/</code>.
            </span>
          </div>
        ) : !detail ? (
          <div className="loading-panel">Loading benchmark data…</div>
        ) : (
          <>
            {selectedRun.source === "overview" ? (
              <div className="overview-banner">
                <strong>Unified evidence</strong>
                <span>
                  Per model: current complete evidence → current partial evidence → legacy complete
                  → legacy partial. Source run and contract state always remain visible.
                </span>
              </div>
            ) : null}

            {selectedContractState === "failed" ? (
              <div className="contract-banner">
                <strong>Inference contract failed</strong>
                <span>
                  Model quality is intentionally N/A.{" "}
                  {selectedPreflight?.error_type ?? selectedPreflight?.status ?? "See diagnostics below."}
                </span>
              </div>
            ) : selectedContractState === "legacy" ? (
              <div className="legacy-banner">
                <strong>Legacy diagnostic evidence</strong>
                <span>
                  This run predates evaluation v3 and can conflate inference failures with model
                  quality. Re-run the model before treating these values as canonical.
                </span>
              </div>
            ) : selectedRun.status === "incomplete" ? (
              <div className="partial-banner">
                <strong>Partial run</strong>
                <span>
                  Metrics are computed from complete JSONL rows already written; provenance remains
                  partial until the run writes its final manifest and metrics.
                </span>
              </div>
            ) : null}

            <section className="run-context">
              {selectedRun.source === "overview" ? (
                <>
                  <div>
                    <span className="eyebrow">Models</span>
                    <strong>{selectedRun.models.length}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Current contract</span>
                    <strong>
                      {selectedRun.models.length - (selectedRun.legacyModels ?? 0)}
                    </strong>
                  </div>
                  <div>
                    <span className="eyebrow">Legacy fallback</span>
                    <strong>{selectedRun.legacyModels ?? 0}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Contract failed</span>
                    <strong>{selectedRun.contractFailedModels ?? 0}</strong>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="eyebrow">Models</span>
                    <strong>{selectedRun.models.length}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Cases</span>
                    <strong>{selectedRun.cases ?? "—"}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Evaluation schema</span>
                    <strong>{selectedRun.evaluationSchema ?? "legacy / unknown"}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Contract</span>
                    <strong>{selectedRun.contractVersion ?? "legacy / unknown"}</strong>
                  </div>
                </>
              )}
            </section>

            <section className="section-heading model-picker-row">
              <div>
                <span className="kicker">Selected model</span>
                <h2>Quality + inference snapshot</h2>
              </div>
              <label className="model-picker">
                <span>Model</span>
                <select
                  value={selectedModel ?? ""}
                  onChange={(event) => setSelectedModel(event.target.value)}
                >
                  {selectedRun.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
            </section>

            <section className="metric-grid">
              <MetricCard
                label="Contract"
                value={contractLabel(selectedContractState)}
                hint={
                  selectedEvidence?.contractVersion ??
                  selectedRun.contractVersion ??
                  "diagnostic"
                }
                tone={selectedContractState === "passed" ? "positive" : "risk"}
              />
              <MetricCard
                label="PII recall"
                value={formatPercent(currentMicro.pii_recall)}
                hint="valid inference only"
                tone="positive"
              />
              <MetricCard
                label="Quality leakage"
                value={formatPercent(currentMicro.leakage_rate)}
                hint="valid inference only"
                tone="risk"
              />
              <MetricCard
                label="System leakage"
                value={formatPercent(
                  currentMicro.system_leakage_rate ?? currentMicro.leakage_rate,
                )}
                hint="includes inference failures"
                tone="risk"
              />
              <MetricCard
                label="Precision"
                value={formatPercent(currentMicro.precision)}
                hint="unresolved values count as FP in v3"
              />
              <MetricCard
                label="Inference success"
                value={formatPercent(
                  currentMicro.inference_success_rate ?? currentMicro.valid_output_rate,
                )}
                hint="valid output contract"
              />
              <MetricCard
                label="Span resolution"
                value={formatPercent(currentMicro.span_resolution_rate)}
                hint="raw items → source spans"
              />
              <MetricCard
                label="Latency p95"
                value={formatMs(latencyP95)}
                hint="valid inference only"
              />
            </section>

            <section className="chart-grid">
              <article className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Trade-off</span>
                    <h2>Recall vs latency</h2>
                  </div>
                  <span className="panel-note">valid quality evidence only</span>
                </div>
                <QualityLatencyChart detail={detail} />
              </article>

              <article className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Coverage</span>
                    <h2>Performance by PII type</h2>
                  </div>
                  <span className="panel-note">{selectedModel}</span>
                </div>
                <PiiChart summary={currentSummary} />
              </article>
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="kicker">All models</span>
                  <h2>Model comparison</h2>
                </div>
                <span className="panel-note">
                  quality and system failures are separated
                </span>
              </div>
              <ModelTable detail={detail} />
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <span className="kicker">Diagnostics</span>
                  <h2>Failure explorer</h2>
                </div>
                <span className="panel-note">
                  {failures.length} case{failures.length === 1 ? "" : "s"}
                </span>
              </div>
              <FailureExplorer failures={failures} />
            </section>

            <section className="manifest-strip">
              <span>
                <strong>Evidence source</strong>
                {selectedEvidence?.suiteId ||
                  selectedEvidence?.runId ||
                  selectedRun.suiteId ||
                  selectedRun.runId ||
                  "—"}
              </span>
              <span>
                <strong>RedactGuard contract</strong>
                {selectedEvidence?.contractVersion ||
                  detail.manifest?.redactguard_contract?.version ||
                  "legacy / unknown"}
              </span>
              <span>
                <strong>Dataset / evidence date</strong>
                {shortDataset(selectedEvidence?.dataset ?? selectedRun.dataset)} ·{" "}
                {formatDate(selectedEvidence?.createdAt ?? selectedRun.createdAt)}
              </span>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
