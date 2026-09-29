/**
 * DocumentAuditHeader.jsx
 *
 * Executive Audit Header providing clear, top-level visual hierarchy:
 * 1. Document context & Model switcher
 * 2. Prominent Safety Verdict (Leak Warning vs Protected Shield)
 * 3. Structured KPI Scorecard (Recall, Leakage Rate, Precision, Total Redactions)
 */

import { memo } from "react";

export const DocumentAuditHeader = memo(function DocumentAuditHeader({
  filename,
  profile,
  goldCount = 0,
  models = [],
  selectedModel,
  onSelectModel,
  activeModelMetrics = null,
  isSplitView = false,
  onToggleSplitView,
  splitModel,
  onSelectSplitModel,
}) {
  const isGoldModel = selectedModel === "__gold__";

  // Normalized metric values
  const recallPct = activeModelMetrics
    ? Math.round(Number(activeModelMetrics.pii_recall ?? activeModelMetrics.recall ?? 0) * 100)
    : null;

  const leakagePct = activeModelMetrics
    ? (Number(activeModelMetrics.leakage_rate ?? activeModelMetrics.leakage ?? 0) * 100).toFixed(1)
    : null;

  const precisionPct = activeModelMetrics
    ? Math.round(Number(activeModelMetrics.precision ?? 0) * 100)
    : null;

  const missedCount = activeModelMetrics?.missedCount ?? 0;
  const overRedactedCount = activeModelMetrics?.overRedactedCount ?? 0;
  const redactionsCount =
    activeModelMetrics?.redactionsCount ?? activeModelMetrics?.identifiedCount ?? 0;

  // File extension badge
  const ext = filename?.split(".").pop()?.toUpperCase() || "DOC";

  return (
    <header className="doc-audit-header" aria-label="Sommario esecutivo dell'audit">
      {/* SEZIONE SUPERIORE: CONTESTO DOCUMENTO & SELEZIONE MODELLO */}
      <div className="audit-header-top">
        <div className="audit-context">
          <div className="audit-file-meta">
            <span className="file-type-pill" data-ext={ext}>
              {ext}
            </span>
            <h2 className="audit-filename" title={filename}>
              {filename}
            </h2>
            {profile && profile !== "generic" && (
              <span className="audit-profile-badge">
                🏷️ {profile}
              </span>
            )}
            <span className="audit-gold-counter">
              🎯 <strong>{goldCount}</strong> PII attesi
            </span>
          </div>

          <div className="audit-model-deck">
            <label className="model-deck-label" htmlFor="header-model-select">
              Modello in esame:
            </label>
            <div className="model-deck-select-wrap">
              <select
                id="header-model-select"
                className="audit-model-select"
                value={selectedModel}
                onChange={(e) => onSelectModel(e.target.value)}
              >
                <option value="__gold__">🎯 Verità di Terra (Gold Standard)</option>
                <optgroup label="Modelli Valutati">
                  {models.map((m) => (
                    <option key={m} value={m}>
                      🤖 {m}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {models.length > 1 && (
              <button
                type="button"
                className={`audit-split-btn ${isSplitView ? "active" : ""}`}
                onClick={onToggleSplitView}
                title="Confronta questo modello con un altro affiancato"
              >
                ⚖️ {isSplitView ? "Chiudi Split" : "Confronto Split"}
              </button>
            )}

            {isSplitView && (
              <div className="audit-split-picker">
                <span>vs</span>
                <select
                  className="audit-model-select split-select"
                  value={splitModel}
                  onChange={(e) => onSelectSplitModel(e.target.value)}
                  aria-label="Secondo modello da comparare"
                >
                  <option value="__gold__">🎯 Ground Truth</option>
                  {models
                    .filter((m) => m !== selectedModel)
                    .map((m) => (
                      <option key={m} value={m}>
                        🤖 {m}
                      </option>
                    ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* VERDETTO DI SICUREZZA (SAFETY VERDICT BADGE) */}
        {!isGoldModel && activeModelMetrics && (
          <div
            className={`audit-verdict-card ${
              missedCount > 0 ? "verdict-card--danger" : "verdict-card--safe"
            }`}
          >
            <div className="verdict-icon">
              {missedCount > 0 ? "⚠️" : "🛡️"}
            </div>
            <div className="verdict-text">
              <span className="verdict-title">
                {missedCount > 0
                  ? `${missedCount} DATI SENSIBILI TRAPELATI (LEAK)`
                  : "ZERO LEAK · 100% PROTETTO"}
              </span>
              <span className="verdict-desc">
                {missedCount > 0
                  ? `Attenzione: ${missedCount} PII sono rimasti visibili in chiaro nel documento!`
                  : "Tutte le entità sensibili attese sono state oscurate dal modello."}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* SEZIONE INFERIORE: SCORECARD KPI GERARCHICO */}
      {!isGoldModel && activeModelMetrics && (
        <div className="audit-scorecard-grid">
          {/* KPI 1: RECALL PII */}
          <div className="kpi-card kpi-card--primary">
            <span className="kpi-label">Recall Copertura PII</span>
            <div className="kpi-value-row">
              <span className="kpi-number">{recallPct}%</span>
              <span className="kpi-badge kpi-badge--info">
                {redactionsCount - overRedactedCount}/{goldCount} protetti
              </span>
            </div>
            <span className="kpi-subtext">Percentuale di PII reali individuati</span>
          </div>

          {/* KPI 2: LEAKAGE RATE */}
          <div
            className={`kpi-card ${
              Number(leakagePct) > 0 ? "kpi-card--danger" : "kpi-card--success"
            }`}
          >
            <span className="kpi-label">Data Leakage Rate</span>
            <div className="kpi-value-row">
              <span className="kpi-number">{leakagePct}%</span>
              {missedCount > 0 ? (
                <span className="kpi-badge kpi-badge--danger">
                  ⚠️ {missedCount} leak
                </span>
              ) : (
                <span className="kpi-badge kpi-badge--success">
                  ✓ 0 leak
                </span>
              )}
            </div>
            <span className="kpi-subtext">
              {missedCount > 0
                ? "Dati sensibili sfuggiti alla redazione"
                : "Nessun dato sensibile trapelato"}
            </span>
          </div>

          {/* KPI 3: PRECISIONE */}
          <div className="kpi-card">
            <span className="kpi-label">Precisione Modello</span>
            <div className="kpi-value-row">
              <span className="kpi-number">{precisionPct}%</span>
              {overRedactedCount > 0 && (
                <span className="kpi-badge kpi-badge--warning">
                  ⚡ {overRedactedCount} extra
                </span>
              )}
            </div>
            <span className="kpi-subtext">
              {overRedactedCount > 0
                ? `${overRedactedCount} entità non-PII sovra-oscurate`
                : "Nessun falso positivo riscontrato"}
            </span>
          </div>

          {/* KPI 4: REDAZIONI TOTALI ESEGUITE */}
          <div className="kpi-card">
            <span className="kpi-label">Redazioni Eseguite</span>
            <div className="kpi-value-row">
              <span className="kpi-number">{redactionsCount}</span>
            </div>
            <span className="kpi-subtext">Elementi totali oscurati dal modello</span>
          </div>
        </div>
      )}
    </header>
  );
});

export default DocumentAuditHeader;
