/**
 * DocumentTextToolbar.jsx
 *
 * Ultra-minimal, single-row primary control bar for document inspection.
 * Combines essential model context, security status, and view controls
 * into a clean, distraction-free 42px header.
 */

import { useState, memo } from "react";

export const DocumentTextToolbar = memo(function DocumentTextToolbar({
  models = [],
  selectedModel,
  onSelectModel,
  activeModelMetrics = null,
  viewMode,
  onChangeViewMode,
  renderStyle = "formatted",
  onChangeRenderStyle,
  isDrawerOpen = false,
  onToggleDrawer,
  disabledTypesCount = 0,
  onCopyRedacted,
  onCopyOriginal,
  searchQuery,
  onSearchChange,
  isFullScreen,
  onToggleFullScreen,
  isSplitView = false,
  onToggleSplitView,
  splitModel,
  onSelectSplitModel,
}) {
  const [copyFeedback, setCopyFeedback] = useState(null);

  const isGold = selectedModel === "__gold__";
  const missedCount = activeModelMetrics?.missedCount ?? 0;
  const overRedactedCount = activeModelMetrics?.overRedactedCount ?? 0;
  const recallPct = activeModelMetrics
    ? Math.round(Number(activeModelMetrics.pii_recall ?? activeModelMetrics.recall ?? 0) * 100)
    : null;

  const handleCopy = async () => {
    if (viewMode === "redacted") {
      await onCopyRedacted();
    } else {
      await onCopyOriginal();
    }
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

  return (
    <div className="doc-minimal-toolbar" role="toolbar" aria-label="Controlli documento">
      {/* SEZIONE SINISTRA: SELEZIONE MODELLO & VERDETTO RAPIDO */}
      <div className="toolbar-sec toolbar-sec--model">
        <div className="minimal-select-box">
          <span className="model-lead-icon">{isGold ? "🎯" : "🤖"}</span>
          <select
            className="minimal-model-select"
            value={selectedModel}
            onChange={(e) => onSelectModel(e.target.value)}
            aria-label="Seleziona modello"
          >
            <option value="__gold__">Ground Truth (Gold)</option>
            <optgroup label="Modelli Testati">
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </optgroup>
          </select>
        </div>

        {/* Status Pill & Recall % */}
        {!isGold && activeModelMetrics && (
          <div className="minimal-meta-strip">
            {missedCount > 0 ? (
              <span
                className="mini-status-pill pill--danger"
                title={`${missedCount} dati sensibili reali non sono stati oscurati (Leak)`}
              >
                ⚠️ {missedCount} {missedCount === 1 ? "leak" : "leak"}
              </span>
            ) : (
              <span
                className="mini-status-pill pill--safe"
                title="Zero dati sensibili trapelati"
              >
                ✓ 0 leak
              </span>
            )}

            {recallPct !== null && (
              <span className="mini-metric-stat" title="Recall di copertura PII">
                <strong>{recallPct}%</strong> recall
              </span>
            )}

            {overRedactedCount > 0 && (
              <span
                className="mini-metric-stat stat--warning"
                title={`${overRedactedCount} entità non-PII sovra-oscurate`}
              >
                ⚡ {overRedactedCount} extra
              </span>
            )}
          </div>
        )}

        {/* Split comparison toggle */}
        {models.length > 1 && (
          <button
            type="button"
            className={`mini-btn ${isSplitView ? "active" : ""}`}
            onClick={onToggleSplitView}
            title="Confronta con un altro modello affiancato"
          >
            ⚖️ Split
          </button>
        )}

        {isSplitView && (
          <select
            className="minimal-model-select mini-split-select"
            value={splitModel}
            onChange={(e) => onSelectSplitModel(e.target.value)}
          >
            <option value="__gold__">🎯 Gold</option>
            {models
              .filter((m) => m !== selectedModel)
              .map((m) => (
                <option key={m} value={m}>
                  🤖 {m}
                </option>
              ))}
          </select>
        )}
      </div>

      {/* SEZIONE CENTRALE: STATO TESTO (OSCURATO / IN CHIARO / AUDIT) */}
      <div className="toolbar-sec toolbar-sec--mode">
        <div className="segmented-control minimal-seg-control" role="group">
          <button
            type="button"
            className={`segment-btn ${viewMode === "redacted" ? "active" : ""}`}
            onClick={() => onChangeViewMode("redacted")}
            title="Visualizza testo con dati sensibili oscurati"
          >
            🛡️ Oscurato
          </button>
          <button
            type="button"
            className={`segment-btn ${viewMode === "revealed" ? "active" : ""}`}
            onClick={() => onChangeViewMode("revealed")}
            title="Visualizza testo originale in chiaro"
          >
            👁️ In Chiaro
          </button>
          <button
            type="button"
            className={`segment-btn ${viewMode === "audit" ? "active" : ""}`}
            onClick={() => onChangeViewMode("audit")}
            title="Audit di sicurezza: evidenzia dati protetti vs leak"
          >
            ⚖️ Audit Leak
          </button>
        </div>
      </div>

      {/* SEZIONE DESTRA: STRUMENTI ESSENZIALI */}
      <div className="toolbar-sec toolbar-sec--tools">
        {/* Ricerca */}
        <div className="mini-search-box">
          <span className="search-ico">🔍</span>
          <input
            type="search"
            className="mini-search-input"
            placeholder="Cerca..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              className="mini-clear-btn"
              onClick={() => onSearchChange("")}
            >
              ✕
            </button>
          )}
        </div>

        {/* Toggle Formattato / Grezzo */}
        <button
          type="button"
          className={`mini-icon-btn ${renderStyle === "formatted" ? "active" : ""}`}
          onClick={() => onChangeRenderStyle(renderStyle === "formatted" ? "raw" : "formatted")}
          title={renderStyle === "formatted" ? "Vista codice grezzo" : "Vista documento formattato"}
        >
          {renderStyle === "formatted" ? "📑" : "🔤"}
        </button>

        {/* Filtri PII per Categoria */}
        <button
          type="button"
          className={`mini-tool-btn ${isDrawerOpen ? "active" : ""} ${
            disabledTypesCount > 0 ? "has-exclusions" : ""
          }`}
          onClick={onToggleDrawer}
          title="Filtri per categoria PII ed opzioni visive"
        >
          🏷️ Filtri
          {disabledTypesCount > 0 && (
            <span className="mini-filter-badge">{disabledTypesCount}</span>
          )}
        </button>

        {/* Copia */}
        <button
          type="button"
          className="mini-tool-btn"
          onClick={handleCopy}
          title="Copia il testo negli appunti"
        >
          📋 {copyFeedback ? "Copiato!" : "Copia"}
        </button>

        {/* Schermo Intero */}
        <button
          type="button"
          className={`mini-icon-btn ${isFullScreen ? "active" : ""}`}
          onClick={onToggleFullScreen}
          title={isFullScreen ? "Esci da Schermo Intero" : "Schermo Intero"}
        >
          {isFullScreen ? "✕" : "⛶"}
        </button>
      </div>
    </div>
  );
});

export default DocumentTextToolbar;
