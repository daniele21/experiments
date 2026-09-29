/**
 * DocumentCategoryFilters.jsx
 *
 * Dedicated collapsible panel for granular PII category filtering and appearance options.
 * Keeps secondary controls neatly organized and separate from primary navigation.
 */

import { memo } from "react";
import { getPiiConfig, documentViewerConfig } from "../config/documentViewerConfig";

export const DocumentCategoryFilters = memo(function DocumentCategoryFilters({
  piiTypesSummary = [],
  disabledTypes = new Set(),
  onToggleType,
  onRedactAll,
  onRevealAll,
  onResetToggles,
  hasUserToggles = false,
  redactionStyle = "blur",
  onChangeRedactionStyle,
  badgeDensity = "compact",
  onChangeBadgeDensity,
}) {
  const disabledCount = disabledTypes.size;
  const totalCategories = piiTypesSummary.length;
  const activeCount = totalCategories - disabledCount;

  return (
    <div className="doc-category-drawer" aria-label="Filtri per categoria PII e opzioni visive">
      <div className="drawer-inner-grid">
        {/* COLONNA 1: CHIP CATEGORIE PII */}
        <div className="drawer-categories-section">
          <div className="drawer-section-header">
            <span className="section-title">
              🏷️ Categorie PII ({activeCount}/{totalCategories} attive)
            </span>
            <span className="section-hint">
              Clicca su una categoria per mostrare/nascondere in chiaro
            </span>
          </div>

          <div className="drawer-chips-wrap">
            {piiTypesSummary.map(({ piiType, count }) => {
              const cfg = getPiiConfig(piiType);
              const isDisabled = disabledTypes.has(piiType);

              return (
                <button
                  key={piiType}
                  type="button"
                  className={`drawer-pii-chip ${isDisabled ? "chip--disabled" : "chip--active"}`}
                  onClick={() => onToggleType(piiType)}
                  style={{
                    "--chip-color": cfg.color,
                    "--chip-bg": cfg.bg,
                    "--chip-border": cfg.border,
                  }}
                  title={
                    isDisabled
                      ? `Clicca per oscurare nuovamente ${cfg.label}`
                      : `Clicca per rivelare in chiaro ${cfg.label}`
                  }
                >
                  <span
                    className="chip-status-dot"
                    style={{ backgroundColor: isDisabled ? "var(--muted)" : cfg.color }}
                  />
                  <span className="chip-icon">{cfg.icon}</span>
                  <span className="chip-name">{cfg.label}</span>
                  <span className="chip-qty">{count}</span>
                  {isDisabled && <span className="chip-in-clear-tag">In chiaro</span>}
                </button>
              );
            })}
          </div>

          {/* Azioni massive rapide */}
          <div className="drawer-bulk-actions">
            <button
              type="button"
              className="drawer-action-btn"
              onClick={onRedactAll}
              title="Oscura tutte le categorie"
            >
              🛡️ Oscura tutte
            </button>
            <span className="sep">•</span>
            <button
              type="button"
              className="drawer-action-btn"
              onClick={onRevealAll}
              title="Rivela tutte le categorie in chiaro"
            >
              👁️ Rivela tutte
            </button>
            {hasUserToggles && (
              <>
                <span className="sep">•</span>
                <button
                  type="button"
                  className="drawer-action-btn drawer-action-btn--reset"
                  onClick={onResetToggles}
                  title="Ripristina lo stato predefinito del modello"
                >
                  ↺ Ripristina predefiniti
                </button>
              </>
            )}
          </div>
        </div>

        {/* COLONNA 2: OPZIONI VISIVE & DENISITÀ ETICHETTE */}
        <div className="drawer-appearance-section">
          <div className="drawer-section-header">
            <span className="section-title">⚙️ Aspetto Visivo & Livello Dettaglio</span>
          </div>

          <div className="drawer-controls-stack">
            {/* Stile Oscuramento */}
            <div className="drawer-control-row">
              <label className="control-label" htmlFor="drawer-style-select">
                Effetto Oscuramento:
              </label>
              <select
                id="drawer-style-select"
                className="drawer-select"
                value={redactionStyle}
                onChange={(e) => onChangeRedactionStyle(e.target.value)}
              >
                {documentViewerConfig.redactionStyles.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.icon} {st.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Densità Etichette Valutazione (✓ Corretto / ⚡ FP / ⚠️ LEAK) */}
            <div className="drawer-control-row">
              <label className="control-label" htmlFor="drawer-density-select">
                Etichette di Valutazione:
              </label>
              <select
                id="drawer-density-select"
                className="drawer-select"
                value={badgeDensity}
                onChange={(e) => onChangeBadgeDensity(e.target.value)}
              >
                {documentViewerConfig.badgeDensities.map((bd) => (
                  <option key={bd.id} value={bd.id}>
                    {bd.icon} {bd.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

export default DocumentCategoryFilters;
