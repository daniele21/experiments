/**
 * App.jsx
 *
 * Main application container for the RedactBench UI.
 * Orchestrates runs list, detail data fetching, auto-refresh cadence,
 * multi-metric scatter plots, and document-level model comparisons.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DocumentComparisonView from "./components/DocumentComparisonView";
import FailureExplorer from "./components/FailureExplorer";
import { MetricCard } from "./components/MetricCard";
import ModelTable from "./components/ModelTable";
import MultiMetricScatterChart from "./components/MultiMetricScatterChart";
import PiiChart from "./components/PiiChart";
import RunList from "./components/RunList";
import TopBar from "./components/TopBar";
import { uiConfig } from "./config/uiConfig";
import { formatDate, formatMs, formatPercent, micro, shortDataset } from "./utils/formatters";

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selectedKey, setSelectedKey] = useState("__overview__");
  const [detail, setDetail] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  // Active top-level view: "models" (Panoramica & Scatter) | "documents" (Confronto per File)
  const [activeView, setActiveView] = useState("models");

  // Loading states:
  // - loadingInitial: True only during the very first bootstrap
  // - loadingDetail: True when switching run keys before any data arrives
  // - isRefreshing: True during silent background polling (keeps existing UI mounted)
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  // User-configurable auto-refresh interval (0 = paused)
  const [refreshInterval, setRefreshInterval] = useState(
    uiConfig.polling.defaultEnabled ? uiConfig.polling.defaultIntervalMs : 0,
  );

  // AbortController ref to cancel obsolete in-flight fetches
  const abortControllerRef = useRef(null);

  /**
   * Fetches data for the given run key and updates runs list.
   * If isBackground is true, avoids blanking the UI with a full-screen loading spinner.
   */
  const fetchData = useCallback(
    async (targetKey, isBackground = false) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      if (!isBackground) {
        setLoadingDetail(true);
      } else {
        setIsRefreshing(true);
      }

      try {
        const endpoint =
          targetKey === "__overview__"
            ? "/api/overview"
            : `/api/run?key=${encodeURIComponent(targetKey)}`;

        // Parallelize runs list refresh and target detail fetching
        const [runsRes, detailRes] = await Promise.all([
          fetch("/api/runs", { cache: "no-store", signal: controller.signal }),
          fetch(endpoint, { cache: "no-store", signal: controller.signal }),
        ]);

        if (!runsRes.ok) throw new Error(`Runs request failed: ${runsRes.status}`);
        if (!detailRes.ok) throw new Error(`Run detail failed: ${detailRes.status}`);

        const runsPayload = await runsRes.json();
        const detailPayload = await detailRes.json();

        setRuns(runsPayload.runs ?? []);
        setDetail(detailPayload);

        // Preserve current model selection if still available, else default to first
        setSelectedModel((current) => {
          const availableModels = detailPayload?.summary?.models ?? [];
          if (current && availableModels.includes(current)) return current;
          return availableModels[0] ?? null;
        });

        setLastRefresh(new Date());
        setError(null);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoadingInitial(false);
          setLoadingDetail(false);
          setIsRefreshing(false);
        }
      }
    },
    [],
  );

  // Fetch when selectedKey changes (user navigates to a new run)
  useEffect(() => {
    fetchData(selectedKey, false);
  }, [selectedKey, fetchData]);

  // Set up background polling interval
  useEffect(() => {
    if (refreshInterval <= 0) return undefined;

    const timer = window.setInterval(() => {
      fetchData(selectedKey, true);
    }, refreshInterval);

    return () => window.clearInterval(timer);
  }, [selectedKey, refreshInterval, fetchData]);

  // Total unique documents across all models in this run
  const documentCount = useMemo(() => {
    if (!detail?.metrics) return 0;
    const docs = new Set();
    for (const m of Object.values(detail.metrics)) {
      if (m?.by_document) {
        for (const k of Object.keys(m.by_document)) {
          docs.add(k);
        }
      }
    }
    return docs.size;
  }, [detail]);

  // Compute derived state for the currently active model and run
  const currentSummary = detail?.metrics?.[selectedModel] ?? null;
  const currentMicro = micro(currentSummary);
  const currentLatency = micro(detail?.latency?.metrics?.[selectedModel]);
  const selectedEvidence = detail?.evidence?.[selectedModel] ?? null;
  const failures = detail?.failures?.[selectedModel] ?? [];

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

  const latencyP50 = currentLatency.latency_p50_ms ?? currentMicro.latency_p50_ms;
  const latencyP95 = currentLatency.latency_p95_ms ?? currentMicro.latency_p95_ms;

  return (
    <div className="app-shell">
      {/* Sidebar navigation */}
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
          <span
            className={`live-dot ${refreshInterval > 0 ? "live-dot--active" : "live-dot--paused"}`}
          >
            <i />
            {refreshInterval > 0
              ? `${uiConfig.polling.intervalOptions.find((o) => o.value === refreshInterval)?.label ?? "auto"}`
              : "off"}
          </span>
        </div>

        {loadingInitial ? (
          <div className="loading-line">Loading runs…</div>
        ) : (
          <RunList runs={runs} selectedKey={selectedKey} onSelect={setSelectedKey} />
        )}
      </aside>

      {/* Main dashboard content */}
      <main className="content">
        <TopBar
          selectedRun={selectedRun}
          lastRefresh={lastRefresh}
          isRefreshing={isRefreshing}
          refreshInterval={refreshInterval}
          onIntervalChange={setRefreshInterval}
          onManualRefresh={() => fetchData(selectedKey, false)}
        />

        {error ? <div className="error-banner">{error}</div> : null}

        {/* Loading detail on initial run load */}
        {loadingDetail && !detail ? (
          <div className="loading-panel">Loading benchmark data…</div>
        ) : !selectedRun ? (
          <div className="empty-state large">
            <strong>No benchmark results found</strong>
            <span>
              The UI reads completed and partial runs directly from <code>results/</code>. No export
              step is required.
            </span>
          </div>
        ) : !detail ? (
          <div className="loading-panel">Loading benchmark data…</div>
        ) : (
          <>
            {/* Status banners */}
            {selectedRun.source === "overview" ? (
              <div className="overview-banner">
                <strong>Unified evidence</strong>
                <span>
                  Each model uses its newest completed benchmark when available. Models without a
                  completed benchmark use the newest partial JSONL evidence and are labelled
                  clearly.
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

            {/* Run Context Header Grid */}
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
                    <strong>
                      {selectedRun.source === "suite" ? "Managed suite" : "Benchmark run"}
                    </strong>
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

            {/* View Switcher: Overall Models vs File-by-File Comparison */}
            <nav className="view-navigation-tabs" aria-label="Modalità di visualizzazione">
              <button
                type="button"
                className={`view-tab ${activeView === "models" ? "active" : ""}`}
                onClick={() => setActiveView("models")}
              >
                <span className="view-tab__icon">📊</span>
                <span>Panoramica Modelli & Scatter</span>
              </button>
              <button
                type="button"
                className={`view-tab ${activeView === "documents" ? "active" : ""}`}
                onClick={() => setActiveView("documents")}
              >
                <span className="view-tab__icon">📑</span>
                <span>Confronto per File</span>
                {documentCount > 0 && (
                  <span className="view-tab__badge">{documentCount} file</span>
                )}
              </button>
            </nav>

            {/* VIEW 1: Overall Models, Multi-Metric Scatter & Diagnostics */}
            {activeView === "models" ? (
              <>
                {/* 1. Overall Models Multi-Metric Scatter Plot */}
                <section className="panel multi-metric-panel">
                  <div className="panel-heading">
                    <div>
                      <span className="kicker">Overall Modelli</span>
                      <h2>Scatter Plot Multi-Metrica</h2>
                    </div>
                    <span className="panel-note">confronto incrociato 2D su tutte le metriche</span>
                  </div>
                  <MultiMetricScatterChart
                    detail={detail}
                    selectedModel={selectedModel}
                    onSelectModel={setSelectedModel}
                  />
                </section>

                {/* 2. Selected Model Quality Snapshot */}
                <section className="section-heading model-picker-row">
                  <div>
                    <span className="kicker">Modello Selezionato</span>
                    <h2>Quality Snapshot</h2>
                  </div>
                  <label className="model-picker">
                    <span>Modello</span>
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

                {/* Metric Cards Grid */}
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
                  <MetricCard
                    label="Latency p50"
                    value={formatMs(latencyP50)}
                    hint="client observed"
                  />
                  <MetricCard
                    label="Latency p95"
                    value={formatMs(latencyP95)}
                    hint="client observed"
                  />
                </section>

                {/* Coverage Chart */}
                <section className="chart-grid">
                  <article className="panel">
                    <div className="panel-heading">
                      <div>
                        <span className="kicker">Coverage</span>
                        <h2>Performance per Tipo PII</h2>
                      </div>
                      <span className="panel-note">{selectedModel}</span>
                    </div>
                    <PiiChart summary={currentSummary} />
                  </article>

                  <article className="panel">
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
                  </article>
                </section>

                {/* Model Comparison Table */}
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <span className="kicker">Tutti i Modelli</span>
                      <h2>Tabella Comparativa</h2>
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
              </>
            ) : (
              /* VIEW 2: Document-by-Document File Comparison View */
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="kicker">Confronto Puntuale</span>
                    <h2>Analisi e Benchmark per Singolo File</h2>
                  </div>
                  <span className="panel-note">
                    {documentCount} file testati su {selectedRun.models.length} modelli
                  </span>
                </div>
                <DocumentComparisonView detail={detail} />
              </section>
            )}

            {/* Run Manifest & Environment Footer */}
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
