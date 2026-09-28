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
        className={selectedKey === "__overview__" ? "run-item overview-item active" : "run-item overview-item"}
        onClick={() => onSelect("__overview__")}
      >
        <div className="run-item__top">
          <strong>All models</strong>
          <span className="pill pill--overview">overview</span>
        </div>
        <span>Unified latest evidence</span>
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
        const dedicatedLatency = micro(detail.latency?.metrics?.[model]);
        const recall = percentValue(quality.pii_recall);
        const latency =
          dedicatedLatency.latency_p95_ms ??
          dedicatedLatency.p95_ms ??
          quality.latency_p95_ms ??
          null;
        if (recall === null || latency === null) return null;
        return { model, recall, latency: Number(latency) };
      })
      .filter(Boolean);
  }, [detail]);

  if (!data.length) {
    return <div className="chart-empty">No comparable recall/latency data for this run.</div>;
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
          labelFormatter={(_, payload) => payload?.[0]?.payload?.model ?? ""}
        />
        <Scatter name="Models" data={data} fill="var(--accent)" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function PiiChart({ summary }) {
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

  if (!rows.length) {
    return <div className="chart-empty">No PII-type breakdown in this run.</div>;
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
        <Bar dataKey="leakage" name="Leakage" fill="var(--risk)" radius={[0, 4, 4, 0]} />
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
            {unified ? <th>Status</th> : null}
            {unified ? <th>Cases</th> : null}
            <th>Recall</th>
            <th>Leakage</th>
            <th>Precision</th>
            <th>Zero leak</th>
            <th>p50</th>
            <th>p95</th>
            {unified ? <th>Source run</th> : null}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => {
            const summary = micro(detail.metrics?.[model]);
            const latency = micro(detail.latency?.metrics?.[model]);
            const evidence = detail.evidence?.[model];
            return (
              <tr key={model}>
                <td className="model-name">{model}</td>
                {unified ? (
                  <td className="status-cell">
                    <span className={evidence?.status === "complete" ? "status-badge status-badge--complete" : "status-badge status-badge--partial"}>
                      {evidence?.status === "complete" ? "complete" : "partial"}
                    </span>
                  </td>
                ) : null}
                {unified ? <td>{evidence?.cases ?? "—"}</td> : null}
                <td>
                  <span>{formatPercent(summary.pii_recall)}</span>
                  <MiniBar value={summary.pii_recall} />
                </td>
                <td>
                  <span>{formatPercent(summary.leakage_rate)}</span>
                  <MiniBar value={summary.leakage_rate} inverse />
                </td>
                <td>
                  <span>{formatPercent(summary.precision)}</span>
                  <MiniBar value={summary.precision} />
                </td>
                <td>{formatPercent(summary.zero_leak_document_rate)}</td>
                <td>{formatMs(latency.latency_p50_ms ?? summary.latency_p50_ms)}</td>
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
        <span>This model has no cases in the failure analysis for the selected run.</span>
      </div>
    );
  }

  return (
    <div className="failure-list">
      {failures.slice(0, 20).map((failure, index) => (
        <details key={`${failure.case_id ?? "case"}-${index}`}>
          <summary>
            <span>
              <strong>{failure.case_id ?? "Unknown case"}</strong>
              <small>
                Recall {formatPercent(failure.pii_recall)} · Leakage{" "}
                {formatPercent(failure.leakage_rate)}
              </small>
            </span>
            <span className="failure-counts">
              FN {failure.fn ?? 0} · FP {failure.fp ?? 0}
            </span>
          </summary>
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
              <span className="eyebrow">Unmatched predictions</span>
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
          {failure.error ? <p className="error-inline">{failure.error}</p> : null}
        </details>
      ))}
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
  }, [selectedKey]);

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

  const latencyP50 = currentLatency.latency_p50_ms ?? currentMicro.latency_p50_ms;
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
                ? "Latest complete evidence per model, with partial evidence used only as fallback."
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
              The UI reads completed and partial runs directly from <code>results/</code>. No
              export step is required.
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
                  Each model uses its newest completed benchmark when available. Models without a
                  completed benchmark use the newest partial JSONL evidence and are labelled clearly.
                </span>
              </div>
            ) : selectedRun.status === "incomplete" ? (
              <div className="partial-banner">
                <strong>Partial run</strong>
                <span>
                  This run did not reach final manifest/metrics generation. The dashboard is
                  calculating provisional metrics directly from the JSONL cases already written.
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
                    <span className="eyebrow">Complete</span>
                    <strong>{selectedRun.completeModels ?? 0}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Partial fallback</span>
                    <strong>{selectedRun.partialModels ?? 0}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Source runs</span>
                    <strong>{selectedRun.sourceRuns ?? 0}</strong>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <span className="eyebrow">Source</span>
                    <strong>{selectedRun.source === "suite" ? "Managed suite" : "Benchmark run"}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">Models</span>
                    <strong>{selectedRun.models.length}</strong>
                  </div>
                  <div>
                    <span className="eyebrow">
                      {selectedRun.status === "incomplete" ? "Completed cases" : "Cases"}
                    </span>
                    <strong>
                      {selectedRun.status === "incomplete"
                        ? selectedRun.completedCasesByModel?.[selectedModel] ??
                          selectedRun.cases ??
                          "—"
                        : selectedRun.cases ?? "—"}
                    </strong>
                  </div>
                  <div>
                    <span className="eyebrow">Status</span>
                    <strong>
                      {selectedRun.status === "incomplete" ? "Partial evidence" : "Complete"}
                    </strong>
                  </div>
                </>
              )}
            </section>

            <section className="section-heading model-picker-row">
              <div>
                <span className="kicker">Selected model</span>
                <h2>Quality snapshot</h2>
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
                label="PII recall"
                value={formatPercent(currentMicro.pii_recall)}
                hint="micro"
                tone="positive"
              />
              <MetricCard
                label="Leakage"
                value={formatPercent(currentMicro.leakage_rate)}
                hint="lower is better"
                tone="risk"
              />
              <MetricCard
                label="Precision"
                value={formatPercent(currentMicro.precision)}
                hint="micro"
              />
              <MetricCard
                label="Zero-leak docs"
                value={formatPercent(currentMicro.zero_leak_document_rate)}
                hint="documents"
              />
              <MetricCard label="Latency p50" value={formatMs(latencyP50)} hint="client observed" />
              <MetricCard label="Latency p95" value={formatMs(latencyP95)} hint="client observed" />
            </section>

            <section className="chart-grid">
              <article className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Trade-off</span>
                    <h2>Recall vs latency</h2>
                  </div>
                  <span className="panel-note">higher / left is better</span>
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
                {detail.evidence ? (
                  <span className="panel-note">latest evidence per model</span>
                ) : detail.latency ? (
                  <span className="panel-note">dedicated latency suite</span>
                ) : (
                  <span className="panel-note">quality-run latency</span>
                )}
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
              {detail.evidence ? (
                <>
                  <span>
                    <strong>Selected model evidence</strong>
                    {selectedEvidence?.suiteId || selectedEvidence?.runId || "—"}
                  </span>
                  <span>
                    <strong>Dataset</strong>
                    {shortDataset(selectedEvidence?.dataset)}
                  </span>
                  <span>
                    <strong>Evidence date</strong>
                    {formatDate(selectedEvidence?.createdAt)}
                  </span>
                </>
              ) : (
                <>
                  <span>
                    <strong>Benchmark commit</strong>
                    {detail.manifest.benchmark_commit ?? "—"}
                  </span>
                  <span>
                    <strong>Korgis</strong>
                    {detail.manifest.korgis?.tested_sha ??
                      detail.manifest.korgis?.source_sha ??
                      "—"}
                  </span>
                  <span>
                    <strong>Host</strong>
                    {detail.manifest.host
                      ? [detail.manifest.host.system, detail.manifest.host.machine]
                          .filter(Boolean)
                          .join(" · ")
                      : "—"}
                  </span>
                </>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
