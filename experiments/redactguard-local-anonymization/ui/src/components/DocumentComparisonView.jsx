import { useMemo, useState } from "react";
import { uiConfig } from "../config/uiConfig";
import { formatMs, formatPercent, micro } from "../utils/formatters";
import { MiniBar } from "./MetricCard";

/**
 * Helper to identify file extension for aesthetic badges.
 */
function getFileBadge(filename) {
  const ext = filename.split(".").pop()?.toUpperCase() ?? "FILE";
  return ext;
}

/**
 * DocumentComparisonView
 *
 * Provides a dedicated, file-by-file comparison of all tested models.
 * Includes search, filtering by profile and leak status, side-by-side model
 * benchmarking per file, and missed spans inspection.
 */
export function DocumentComparisonView({ detail }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [viewMode, setViewMode] = useState("cards"); // "cards" | "matrix"

  const models = useMemo(() => detail?.summary?.models ?? [], [detail]);

  // Aggregate files across all models
  const { filesList, profilesList } = useMemo(() => {
    if (!detail?.metrics) return { filesList: [], profilesList: [] };

    const fileMap = new Map();
    const profiles = new Set();

    for (const model of models) {
      const byDoc = detail.metrics[model]?.by_document ?? {};
      for (const [filename, docMetrics] of Object.entries(byDoc)) {
        if (!docMetrics) continue;

        if (docMetrics.profile) {
          profiles.add(docMetrics.profile);
        }

        if (!fileMap.has(filename)) {
          fileMap.set(filename, {
            filename,
            extension: getFileBadge(filename),
            profile: docMetrics.profile ?? "generic",
            tags: docMetrics.tags ?? [],
            goldCount: docMetrics.gold_count ?? 0,
            goldChars: docMetrics.gold_chars ?? 0,
            modelsData: {},
          });
        }

        const entry = fileMap.get(filename);
        entry.modelsData[model] = docMetrics;
        // Keep the largest gold count if any model reports it more accurately
        if (docMetrics.gold_count > entry.goldCount) {
          entry.goldCount = docMetrics.gold_count;
        }
        if (docMetrics.gold_chars > entry.goldChars) {
          entry.goldChars = docMetrics.gold_chars;
        }
      }
    }

    const files = Array.from(fileMap.values()).map((file) => {
      // Determine overall document difficulty & best model
      const modelScores = Object.entries(file.modelsData);
      let bestModel = null;
      let highestRecall = -1;
      let lowestLeakage = 2;
      let hasAnyLeak = false;
      let allZeroLeak = modelScores.length > 0;

      for (const [mName, mData] of modelScores) {
        const recall = Number(mData.pii_recall ?? 0);
        const leakage = Number(mData.leakage_rate ?? 0);
        if (leakage > 0) hasAnyLeak = true;
        if (leakage > 0) allZeroLeak = false;

        // Best model criteria: highest recall, then lowest leakage
        if (
          recall > highestRecall ||
          (recall === highestRecall && leakage < lowestLeakage)
        ) {
          highestRecall = recall;
          lowestLeakage = leakage;
          bestModel = mName;
        }
      }

      return {
        ...file,
        bestModel,
        hasAnyLeak,
        allZeroLeak,
        testedModelsCount: modelScores.length,
      };
    });

    // Sort files alphabetically by default
    files.sort((a, b) => a.filename.localeCompare(b.filename));

    return {
      filesList: files,
      profilesList: Array.from(profiles).sort(),
    };
  }, [detail, models]);

  // Filtered files
  const filteredFiles = useMemo(() => {
    return filesList.filter((file) => {
      // Search text match
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = file.filename.toLowerCase().includes(query);
        const matchesTag = file.tags.some((t) => t.toLowerCase().includes(query));
        if (!matchesName && !matchesTag) return false;
      }

      // Profile match
      if (selectedProfile !== "all" && file.profile !== selectedProfile) {
        return false;
      }

      // Status match
      if (statusFilter === "leaks_only" && !file.hasAnyLeak) {
        return false;
      }
      if (statusFilter === "zero_leak_only" && !file.allZeroLeak) {
        return false;
      }
      if (statusFilter === "discrepancies") {
        // Files where models performed differently
        const recalls = Object.values(file.modelsData).map((m) =>
          Number(m.pii_recall ?? 0).toFixed(2),
        );
        const uniqueRecalls = new Set(recalls);
        if (uniqueRecalls.size <= 1) return false;
      }

      return true;
    });
  }, [filesList, searchQuery, selectedProfile, statusFilter]);

  // Toggle accordion card expansion
  const toggleExpand = (filename) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) {
        next.delete(filename);
      } else {
        next.add(filename);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedFiles(new Set(filteredFiles.map((f) => f.filename)));
  };

  const collapseAll = () => {
    setExpandedFiles(new Set());
  };

  if (!filesList.length) {
    return (
      <div className="empty-state">
        <strong>Nessun documento trovato</strong>
        <span>
          Non sono presenti informazioni per documento nel benchmark selezionato.
        </span>
      </div>
    );
  }

  // Summary counts
  const totalFiles = filesList.length;
  const zeroLeakCount = filesList.filter((f) => f.allZeroLeak).length;
  const filesWithLeaks = filesList.filter((f) => f.hasAnyLeak).length;

  return (
    <div className="doc-comparison-view">
      {/* Overview Stats Bar */}
      <section className="doc-stats-grid">
        <div className="doc-stat-card">
          <span className="eyebrow">Documenti Totali</span>
          <strong>{totalFiles}</strong>
          <small>file analizzati</small>
        </div>
        <div className="doc-stat-card doc-stat-card--positive">
          <span className="eyebrow">Zero Leak Totale</span>
          <strong>{zeroLeakCount}</strong>
          <small>tutti i modelli sicuri</small>
        </div>
        <div className="doc-stat-card doc-stat-card--risk">
          <span className="eyebrow">File Con Leak</span>
          <strong>{filesWithLeaks}</strong>
          <small>almeno un modello perde dati</small>
        </div>
        <div className="doc-stat-card">
          <span className="eyebrow">Modelli Comparati</span>
          <strong>{models.length}</strong>
          <small>per ogni documento</small>
        </div>
      </section>

      {/* Filter and Search Bar */}
      <div className="doc-filters-bar">
        <div className="doc-search-box">
          <span className="search-icon">🔍</span>
          <input
            type="search"
            placeholder="Cerca per nome file o tag (es. pdf, contratto, xlsx)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Cerca file"
          />
          {searchQuery && (
            <button
              type="button"
              className="clear-search"
              onClick={() => setSearchQuery("")}
            >
              ✕
            </button>
          )}
        </div>

        <div className="doc-filter-controls">
          <label className="filter-select">
            <span>Profilo:</span>
            <select
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(e.target.value)}
            >
              <option value="all">Tutti i profili</option>
              {profilesList.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>

          <label className="filter-select">
            <span>Filtra:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">Tutti i file ({filesList.length})</option>
              <option value="leaks_only">Solo file con Leak ({filesWithLeaks})</option>
              <option value="zero_leak_only">Solo Zero Leak ({zeroLeakCount})</option>
              <option value="discrepancies">Solo con discrepanze tra modelli</option>
            </select>
          </label>

          <div className="view-mode-toggle">
            <button
              type="button"
              className={viewMode === "cards" ? "active" : ""}
              onClick={() => setViewMode("cards")}
              title="Vista a schede dettagliate"
            >
              Schede
            </button>
            <button
              type="button"
              className={viewMode === "matrix" ? "active" : ""}
              onClick={() => setViewMode("matrix")}
              title="Vista matrice compatta"
            >
              Matrice
            </button>
          </div>
        </div>
      </div>

      {/* Accordion actions */}
      {viewMode === "cards" && (
        <div className="doc-accordion-actions">
          <span className="results-count">
            Mostrati <strong>{filteredFiles.length}</strong> su {totalFiles} file
          </span>
          <div className="expand-buttons">
            <button type="button" onClick={expandAll}>
              Espandi tutti
            </button>
            <button type="button" onClick={collapseAll}>
              Comprimi tutti
            </button>
          </div>
        </div>
      )}

      {/* No Results */}
      {!filteredFiles.length ? (
        <div className="empty-state">
          <strong>Nessun file corrisponde ai filtri</strong>
          <span>Prova a modificare la ricerca o i filtri selezionati.</span>
        </div>
      ) : viewMode === "matrix" ? (
        /* ================= VISTA MATRICE COMPATTA ================= */
        <div className="table-scroll doc-matrix-wrapper">
          <table className="comparison-table doc-matrix-table">
            <thead>
              <tr>
                <th className="sticky-col">Documento</th>
                <th>Profilo</th>
                <th>PII Gold</th>
                {models.map((model) => (
                  <th key={model} className="model-col-header">
                    {model}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredFiles.map((file) => (
                <tr key={file.filename}>
                  <td className="sticky-col doc-matrix-title">
                    <span className="file-badge">{file.extension}</span>
                    <strong title={file.filename}>{file.filename}</strong>
                  </td>
                  <td>
                    <span className="profile-tag">{file.profile}</span>
                  </td>
                  <td>{file.goldCount}</td>
                  {models.map((model) => {
                    const data = file.modelsData[model];
                    if (!data) {
                      return (
                        <td key={model} className="matrix-cell-empty">
                          —
                        </td>
                      );
                    }
                    const isZeroLeak = Number(data.leakage_rate ?? 0) === 0;
                    return (
                      <td key={model} className="matrix-model-cell">
                        <div className="matrix-score">
                          <span className="matrix-recall">
                            {formatPercent(data.pii_recall)}
                          </span>
                          <span
                            className={`status-badge ${
                              isZeroLeak
                                ? "status-badge--complete"
                                : "status-badge--partial"
                            }`}
                          >
                            {isZeroLeak
                              ? "0% leak"
                              : `${formatPercent(data.leakage_rate)} leak`}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* ================= VISTA SCHEDE DETTAGLIATE ================= */
        <div className="doc-cards-list">
          {filteredFiles.map((file) => {
            const isExpanded = expandedFiles.has(file.filename);
            return (
              <div
                key={file.filename}
                className={`doc-card ${isExpanded ? "doc-card--expanded" : ""}`}
              >
                {/* Header della Scheda File */}
                <div
                  className="doc-card-header"
                  onClick={() => toggleExpand(file.filename)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      toggleExpand(file.filename);
                    }
                  }}
                >
                  <div className="doc-card-title-group">
                    <span className="file-badge">{file.extension}</span>
                    <div>
                      <h3 className="doc-card-title">{file.filename}</h3>
                      <div className="doc-card-meta">
                        <span className="profile-tag">{file.profile}</span>
                        <span>Gold PII: {file.goldCount}</span>
                        <span>Caratteri PII: {file.goldChars}</span>
                        {file.allZeroLeak ? (
                          <span className="pill pill--zero-leak">
                            🛡️ Zero Leak (Tutti)
                          </span>
                        ) : file.hasAnyLeak ? (
                          <span className="pill pill--partial">
                            ⚠️ Presenza Leak
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  <div className="doc-card-header-right">
                    {file.bestModel && (
                      <span
                        className="best-model-badge"
                        title={`Miglior performance su questo file: ${file.bestModel}`}
                      >
                        🏆 {file.bestModel}
                      </span>
                    )}
                    <span className="accordion-arrow">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </div>
                </div>

                {/* Tabella Comparativa Modelli per questo File */}
                <div className="doc-card-body">
                  <div className="table-scroll">
                    <table className="comparison-table doc-model-table">
                      <thead>
                        <tr>
                          <th>Modello</th>
                          <th>Recall PII</th>
                          <th>Leakage</th>
                          <th>Precision</th>
                          <th>Span F1</th>
                          <th>Zero Leak</th>
                          <th>Latenza</th>
                          <th>Missed (FN)</th>
                          <th>Over-redacted (FP)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {models.map((model) => {
                          const mData = file.modelsData[model];
                          if (!mData) {
                            return (
                              <tr key={model}>
                                <td className="model-name">{model}</td>
                                <td colSpan={8} className="muted">
                                  Non testato su questo documento
                                </td>
                              </tr>
                            );
                          }

                          const isZero = Number(mData.leakage_rate ?? 0) === 0;
                          const isBest = file.bestModel === model;

                          return (
                            <tr
                              key={model}
                              className={isBest ? "row-highlight" : ""}
                            >
                              <td className="model-name">
                                {model}
                                {isBest && (
                                  <span
                                    className="best-star"
                                    title="Miglior modello per questo file"
                                  >
                                    {" "}
                                    ★
                                  </span>
                                )}
                              </td>
                              <td>
                                <span>{formatPercent(mData.pii_recall)}</span>
                                <MiniBar value={mData.pii_recall} />
                              </td>
                              <td>
                                <span>{formatPercent(mData.leakage_rate)}</span>
                                <MiniBar
                                  value={mData.leakage_rate}
                                  inverse
                                />
                              </td>
                              <td>
                                <span>{formatPercent(mData.precision)}</span>
                                <MiniBar value={mData.precision} />
                              </td>
                              <td>{formatPercent(mData.span_f1)}</td>
                              <td>
                                <span
                                  className={`status-badge ${
                                    isZero
                                      ? "status-badge--complete"
                                      : "status-badge--partial"
                                  }`}
                                >
                                  {isZero ? "Zero Leak" : "Leaked"}
                                </span>
                              </td>
                              <td>
                                {formatMs(
                                  mData.latency_p50_ms ?? mData.latency_ms,
                                )}
                              </td>
                              <td
                                className={
                                  (mData.fn ?? 0) > 0 ? "fn-count-risk" : ""
                                }
                              >
                                {mData.fn ?? 0}
                              </td>
                              <td
                                className={
                                  (mData.fp ?? 0) > 0 ? "fp-count-risk" : ""
                                }
                              >
                                {mData.fp ?? 0}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Ispettore Dettagliato Spans (Espandibile) */}
                  {isExpanded && (
                    <div className="doc-spans-inspector">
                      <h4 className="inspector-heading">
                        Dettaglio Entità Mancate o Errate per Modello
                      </h4>
                      <div className="inspector-models-grid">
                        {models.map((model) => {
                          const mData = file.modelsData[model];
                          if (!mData) return null;
                          const fnSpans = mData.false_negatives ?? [];
                          const fpSpans = mData.false_positives ?? [];

                          return (
                            <div key={model} className="inspector-model-card">
                              <div className="inspector-model-title">
                                <strong>{model}</strong>
                                <small>
                                  FN: {fnSpans.length} · FP: {fpSpans.length}
                                </small>
                              </div>

                              <div className="spans-section">
                                <span className="eyebrow">
                                  Mancati (False Negatives):
                                </span>
                                {fnSpans.length ? (
                                  <ul className="spans-list">
                                    {fnSpans
                                      .slice(
                                        0,
                                        uiConfig.fileComparison.maxVisibleSpans,
                                      )
                                      .map((item, idx) => (
                                        <li key={idx}>
                                          <code>{item.pii_type ?? "PII"}</code>{" "}
                                          <span>{item.value || "—"}</span>
                                        </li>
                                      ))}
                                    {fnSpans.length >
                                      uiConfig.fileComparison
                                        .maxVisibleSpans && (
                                      <li className="muted">
                                        + altri{" "}
                                        {fnSpans.length -
                                          uiConfig.fileComparison
                                            .maxVisibleSpans}{" "}
                                        elementi...
                                      </li>
                                    )}
                                  </ul>
                                ) : (
                                  <p className="no-errors-text">
                                    ✓ Nessuna entità PII persa
                                  </p>
                                )}
                              </div>

                              {fpSpans.length > 0 && (
                                <div className="spans-section">
                                  <span className="eyebrow">
                                    Sovra-oscurati (False Positives):
                                  </span>
                                  <ul className="spans-list">
                                    {fpSpans
                                      .slice(
                                        0,
                                        uiConfig.fileComparison.maxVisibleSpans,
                                      )
                                      .map((item, idx) => (
                                        <li key={idx}>
                                          <code>
                                            {item.pii_type ?? "PII"}
                                          </code>{" "}
                                          <span>{item.value || "—"}</span>
                                        </li>
                                      ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DocumentComparisonView;
