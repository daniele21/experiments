/**
 * App.jsx
 *
 * Main application container for the RedactBench UI.
 * Orchestrates runs list, detail data fetching, auto-refresh cadence,
 * multi-metric scatter plots, document-level model comparisons,
 * and RedactGuard v3 contract & system-failure awareness.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ClientEvaluationJourney from "./components/ClientEvaluationJourney";
import DocumentComparisonView from "./components/DocumentComparisonView";
import ExecutiveBriefingView from "./components/ExecutiveBriefingView";
import FailureExplorer from "./components/FailureExplorer";
import { MetricCard } from "./components/MetricCard";
import ModelTable from "./components/ModelTable";
import MultiMetricScatterChart from "./components/MultiMetricScatterChart";
import PiiChart from "./components/PiiChart";
import QualityLatencyChart from "./components/QualityLatencyChart";
import RunList from "./components/RunList";
import TopBar from "./components/TopBar";
import { uiConfig } from "./config/uiConfig";
import { formatDate, formatMs, formatPercent, micro, shortDataset } from "./utils/formatters";

function contractState(metrics, evidence, summary) {
  if (evidence?.contractStatus) return evidence.contractStatus;
  if (metrics?.status === "contract_failed") return "failed";
  if (summary?.legacy || evidence?.legacy) return "legacy";
  return "passed";
}

function contractLabel(state) {
  if (state === "failed") return "Contract failed";
  if (state === "legacy") return "Legacy schema";
  return "Contract verified";
}

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selectedKey, setSelectedKey] = useState("__overview__");
  const [detail, setDetail] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  // Client-facing evaluation is the primary surface. Technical benchmark
  // workspaces are intentionally nested under Advanced.
  const [activeView, setActiveView] = useState("client");
  const [advancedView, setAdvancedView] = useState("executive");

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

  const selectedContractState = contractState(
    detail?.metrics?.[selectedModel],
    selectedEvidence,
    selectedRun,
  );

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
            {/* Status banners: advanced evidence context only */}
            {activeView === "advanced" && (selectedRun.legacy ? (
              <div className="legacy-banner">
                <strong>Legacy evaluation schema</strong>
                <span>
                  This run predates RedactGuard evaluation v3. Contract validation and inference
                  failures were not separated from model quality. Re-run the model before treating
                  these values as canonical.
                </span>
              </div>
            ) : selectedContractState === "failed" ? (
              <div className="error-banner">
                <strong>Inference contract failure</strong>
                <span>
                  The model produced outputs that violated the required RedactGuard contract or
                  fell back during structured parsing. System metrics capture this as operational
                  risk; quality metrics are suppressed.
                </span>
              </div>
            ) : selectedRun.source === "overview" ? (
              <div className="overview-banner">
                <strong>Unified evidence</strong>
                <span>
                  Each model uses its newest complete run when available, falling back to partial
                  evidence. Legacy schema runs and contract failures are quarantined and labelled.
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
            ) : null)}

            {/* Run Context Header Grid */}
            {activeView === "advanced" ? (
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
            ) : null}

            {/* Primary client/advanced navigation */}
            <nav className="view-navigation-tabs view-tabs client-primary-tabs" aria-label="Dashboard mode">
              <button
                type="button"
                className={`view-tab ${activeView === "client" ? "active" : ""}`}
                onClick={() => setActiveView("client")}
              >
                <span className="view-tab__icon">🛡️</span>
                <span>Client Evaluation</span>
              </button>
              <button
                type="button"
                className={`view-tab ${activeView === "advanced" ? "active" : ""}`}
                onClick={() => setActiveView("advanced")}
              >
                <span className="view-tab__icon">⚙️</span>
                <span>Advanced analysis</span>
              </button>
            </nav>

            {activeView === "advanced" ? (
              <nav className="advanced-view-tabs" aria-label="Advanced analysis section">
                <button
                  type="button"
                  className={advancedView === "executive" ? "active" : ""}
                  onClick={() => setAdvancedView("executive")}
                >
                  Executive benchmark
                </button>
                <button
                  type="button"
                  className={advancedView === "models" ? "active" : ""}
                  onClick={() => setAdvancedView("models")}
                >
                  Technical workbench
                </button>
                <button
                  type="button"
                  className={advancedView === "documents" ? "active" : ""}
                  onClick={() => setAdvancedView("documents")}
                >
                  Gold-aware document audit
                  {documentCount > 0 ? <span>{documentCount}</span> : null}
                </button>
              </nav>
            ) : null}

            {/* Primary progressive-disclosure client journey */}
            {activeView === "client" ? (
              <ClientEvaluationJourney
                detail={detail}
                selectedModel={selectedModel}
                onSelectModel={setSelectedModel}
              />
            ) : advancedView === "executive" ? (
              <ExecutiveBriefingView
                detail={detail}
                selectedRun={selectedRun}
                selectedModel={selectedModel}
                onSelectModel={setSelectedModel}
                onNavigateToDocuments={() => setAdvancedView("documents")}
              />
            ) : advancedView === "models" ? (
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

                {/* Metric Cards Grid */}
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

                {/* Trade-off & Coverage Charts */}
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

                {/* Model Comparison Table */}
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

                {/* Failure Explorer */}
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <span className="kicker">Diagnostics</span>
                      <h2>Failure explorer</h2>
                    </div>
                    <span className="panel-note">
                      {failures.length} caso/i per {selectedModel ?? "modello"}
                    </span>
                  </div>
                  <FailureExplorer
                    failures={failures}
                    selectedModel={selectedModel}
                    models={selectedRun.models}
                    allFailures={detail?.failures}
                    onSelectModel={setSelectedModel}
                  />
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

            {/* Run Manifest & Environment Footer: advanced provenance only */}
            {activeView === "advanced" ? (
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
            ) : null}
          </>
        )}
      </main>
    </div>
  );
}
