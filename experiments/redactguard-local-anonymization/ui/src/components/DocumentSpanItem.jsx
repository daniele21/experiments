/**
 * DocumentSpanItem.jsx
 *
 * Minimalist, distraction-free PII span component.
 * In redacted view:
 * - True Positives are cleanly blurred with subtle styling (no badge spam).
 * - False Positives have a discrete warning marker.
 * - Leaks (False Negatives) stand out prominently in clear text with a red warning badge.
 * - Full forensic details appear cleanly in the floating tooltip on hover.
 */

import { useState, memo } from "react";
import { getPiiConfig, documentViewerConfig } from "../config/documentViewerConfig";
import { formatRedactionPlaceholder } from "../utils/textRedactor";

export const DocumentSpanItem = memo(function DocumentSpanItem({
  span,
  style = "blur",
  density = "compact", // "compact" (minimal) | "full" | "leak_only"
  onToggle,
  isToggledByUser = false,
}) {
  const [showTooltip, setShowTooltip] = useState(false);

  const piiCfg = getPiiConfig(span.pii_type);
  const statusCfg = documentViewerConfig.statusConfig[span.status] || null;

  const isRedacted = span.isRedacted;
  const isBlur = style === "blur";

  const placeholderText = formatRedactionPlaceholder(span, style);

  // Status visual classification
  const isLeak = span.status === "fn";
  const isExtra = span.status === "fp";
  const isTp = span.status === "tp";
  const isGold = span.status === "gold";

  return (
    <span
      className={`doc-span-wrapper ${isRedacted ? "doc-span--redacted" : "doc-span--revealed"} ${
        isToggledByUser ? "doc-span--user-toggled" : ""
      } ${isLeak ? "doc-span--leak" : ""} ${isExtra ? "doc-span--extra" : ""}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onClick={(e) => {
        e.stopPropagation();
        onToggle?.(span.id);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle?.(span.id);
        }
      }}
      title={`Clicca per ${isRedacted ? "rivelare" : "oscurare"} (${piiCfg.label})`}
    >
      {isRedacted ? (
        // ================= STATO OSCURATO (PULITO & MINIMAL) =================
        <span
          className={`doc-redacted-badge doc-redacted--${style} ${
            isTp ? "doc-redacted--correct" : isExtra ? "doc-redacted--wrong" : ""
          }`}
          style={{
            "--pii-color": piiCfg.color,
            "--pii-bg": piiCfg.bg,
          }}
        >
          {isBlur ? (
            <span className="blur-content">{span.content}</span>
          ) : style === "pill" ? (
            <span className="pill-content">
              <span className="pill-icon">{piiCfg.icon}</span>
              <span className="pill-type">{piiCfg.label.toUpperCase()}</span>
            </span>
          ) : (
            <span className="block-content">{placeholderText}</span>
          )}

          {/* Dettagli inline solo su richiesta esplicita (full) o per anomalie (extra) */}
          {density === "full" ? (
            <>
              {isTp && (
                <span
                  className="doc-eval-tag eval-tag--correct"
                  title="Oscuramento corretto (True Positive)"
                >
                  <span className="eval-icon">✓</span>
                  <span className="eval-text">Corretto</span>
                </span>
              )}
              {isExtra && (
                <span
                  className="doc-eval-tag eval-tag--wrong"
                  title="Falso positivo: non è un dato sensibile reale"
                >
                  <span className="eval-icon">⚡</span>
                  <span className="eval-text">Extra</span>
                </span>
              )}
            </>
          ) : isExtra ? (
            /* In vista compatta/normale, solo i falsi positivi hanno un discreto marcatore */
            <span
              className="doc-eval-dot dot--warning"
              title="Falso positivo: oscurato per errore (non è un PII reale)"
            >
              ⚡
            </span>
          ) : null}

          {isToggledByUser && (
            <span className="user-toggle-dot" title="Modificato manualmente dall'utente" />
          )}
        </span>
      ) : (
        // ================= STATO IN CHIARO (REVEALED / HIGHLIGHTED) =================
        <mark
          className={`doc-revealed-mark ${isLeak ? "mark-leak" : ""} ${
            isExtra ? "mark-extra" : ""
          } ${isTp ? "mark-tp" : ""} ${isGold ? "mark-gold" : ""}`}
          style={{
            backgroundColor: isLeak
              ? "rgba(239, 68, 68, 0.18)"
              : isExtra
              ? "rgba(245, 158, 11, 0.18)"
              : piiCfg.bg,
            borderColor: isLeak
              ? "#ef4444"
              : isExtra
              ? "#f59e0b"
              : piiCfg.border,
            color: "var(--text, #172033)",
          }}
        >
          <span className="mark-text">{span.content}</span>
          <span
            className={`mark-tag ${
              isLeak
                ? "tag-leak"
                : isExtra
                ? "tag-warning"
                : isTp
                ? "tag-correct"
                : ""
            }`}
            style={{
              backgroundColor: isLeak
                ? "#ef4444"
                : isExtra
                ? "#f59e0b"
                : isTp
                ? "#10b981"
                : piiCfg.color,
              color: "#ffffff",
            }}
          >
            {isLeak
              ? "⚠️ LEAK"
              : isExtra
              ? "⚡ Extra"
              : isTp
              ? `✓ ${piiCfg.label}`
              : `${piiCfg.icon} ${piiCfg.label}`}
          </span>
          {isToggledByUser && (
            <span className="user-toggle-dot" title="Modificato manualmente dall'utente" />
          )}
        </mark>
      )}

      {/* TOOLTIP DETTAGLIATO AL PASSAGGIO DEL MOUSE */}
      {showTooltip && (
        <span className="span-floating-tooltip" role="tooltip">
          <span className="tooltip-header">
            <span className="tooltip-type-pill" style={{ backgroundColor: piiCfg.color }}>
              {piiCfg.icon} {piiCfg.label}
            </span>
            <span className="tooltip-action-hint">
              {isRedacted ? "🔓 Clicca per rivelare" : "🔒 Clicca per oscurare"}
            </span>
          </span>

          <span className="tooltip-row">
            <span className="tooltip-label">Valore originale:</span>
            <code className="tooltip-value">{span.value}</code>
          </span>

          <span className="tooltip-row">
            <span className="tooltip-label">Posizione:</span>
            <span className="tooltip-coords">
              {span.start} - {span.end} ({span.end - span.start} car.)
            </span>
          </span>

          {/* Valutazione di correttezza chiara ed esplicita */}
          {isTp && (
            <span className="tooltip-status status-tp">
              <span className="status-icon">✓</span>
              <span><strong>Oscuramento Corretto:</strong> PII reale rimosso con successo dal modello.</span>
            </span>
          )}
          {isExtra && (
            <span className="tooltip-status status-fp">
              <span className="status-icon">⚡</span>
              <span><strong>Falso Positivo:</strong> Testo oscurato per errore (non presente nei PII attesi).</span>
            </span>
          )}
          {isLeak && (
            <span className="tooltip-status status-fn">
              <span className="status-icon">⚠️</span>
              <span><strong>PII MANCATO (LEAK):</strong> Questo dato sensibile reale NON è stato oscurato ed è trapelato!</span>
            </span>
          )}
          {isGold && (
            <span className="tooltip-status status-gold">
              <span className="status-icon">🎯</span>
              <span><strong>Target Gold Standard:</strong> Entità sensibile di riferimento.</span>
            </span>
          )}

          {isToggledByUser && (
            <span className="tooltip-manual-note">
              ✏️ Modificato manualmente dall'utente
            </span>
          )}
        </span>
      )}
    </span>
  );
});

export default DocumentSpanItem;
