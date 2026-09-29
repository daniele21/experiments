/**
 * documentViewerConfig.js
 *
 * Configuration for document visualization, PII color schemes,
 * redaction placeholders, and interactive inspection options.
 */

export const piiTypeConfig = {
  private_person: {
    label: "Persona",
    icon: "👤",
    color: "#3b82f6", // Vibrant Blue
    bg: "rgba(59, 130, 246, 0.15)",
    border: "rgba(59, 130, 246, 0.35)",
    textOnDark: "#93c5fd",
  },
  private_email: {
    label: "Email",
    icon: "✉️",
    color: "#10b981", // Emerald Green
    bg: "rgba(16, 185, 129, 0.15)",
    border: "rgba(16, 185, 129, 0.35)",
    textOnDark: "#6ee7b7",
  },
  private_phone: {
    label: "Telefono",
    icon: "📞",
    color: "#f59e0b", // Amber / Warm Orange
    bg: "rgba(245, 158, 11, 0.15)",
    border: "rgba(245, 158, 11, 0.35)",
    textOnDark: "#fcd34d",
  },
  account_number: {
    label: "Conto / IBAN / CF",
    icon: "💳",
    color: "#8b5cf6", // Violet / Purple
    bg: "rgba(139, 92, 246, 0.15)",
    border: "rgba(139, 92, 246, 0.35)",
    textOnDark: "#c4b5fd",
  },
  private_address: {
    label: "Indirizzo",
    icon: "📍",
    color: "#ec4899", // Rose / Pink
    bg: "rgba(236, 72, 153, 0.15)",
    border: "rgba(236, 72, 153, 0.35)",
    textOnDark: "#f472b6",
  },
  private_date: {
    label: "Data",
    icon: "📅",
    color: "#06b6d4", // Cyan
    bg: "rgba(6, 182, 212, 0.15)",
    border: "rgba(6, 182, 212, 0.35)",
    textOnDark: "#67e8f9",
  },
  secret: {
    label: "Segreto / PIN",
    icon: "🔒",
    color: "#ef4444", // Crimson Red
    bg: "rgba(239, 68, 68, 0.18)",
    border: "rgba(239, 68, 68, 0.4)",
    textOnDark: "#fca5a5",
  },
  personal_demographic: {
    label: "Dati Demografici",
    icon: "👥",
    color: "#6366f1", // Indigo
    bg: "rgba(99, 102, 241, 0.15)",
    border: "rgba(99, 102, 241, 0.35)",
    textOnDark: "#a5b4fc",
  },
  default: {
    label: "Dato Sensibile",
    icon: "🏷️",
    color: "#64748b", // Slate
    bg: "rgba(100, 116, 139, 0.15)",
    border: "rgba(100, 116, 139, 0.35)",
    textOnDark: "#cbd5e1",
  },
};

/**
 * Returns configuration metadata for a given PII type string.
 */
export function getPiiConfig(piiType) {
  if (!piiType) return piiTypeConfig.default;
  const key = String(piiType).toLowerCase().trim();
  return piiTypeConfig[key] || piiTypeConfig.default;
}

export const documentViewerConfig = {
  // Available visual redaction styles
  redactionStyles: [
    { id: "block", label: "Blocco Solido (███)", icon: "⬛" },
    { id: "pill", label: "Badge Pill [TIPO]", icon: "🏷️" },
    { id: "blur", label: "Effetto Blur", icon: "💧" },
    { id: "mask", label: "Mascheramento (***)", icon: "✱" },
  ],

  // Badge density levels for information hierarchy
  badgeDensities: [
    { id: "full", label: "Complete (Testo + Icone)", shortLabel: "Dettagliate", icon: "🏷️" },
    { id: "compact", label: "Compatte (Solo Icone ✓ / ⚡)", shortLabel: "Compatte", icon: "🔹" },
    { id: "leak_only", label: "Solo Leak (Pulisce la tabella)", shortLabel: "Solo Leak", icon: "⚠️" },
  ],

  // Default viewer preferences
  defaults: {
    viewMode: "redacted", // "redacted" | "revealed" | "audit"
    redactionStyle: "blur",
    badgeDensity: "compact", // "compact" | "full" | "leak_only"
    showLineNumbers: true,
    fontSize: "13px",
  },

  // Status badges for evaluation
  statusConfig: {
    tp: {
      label: "Oscurato con successo",
      badgeClass: "status-tp",
      icon: "✓",
      description: "Il modello ha identificato e rimosso correttamente questo dato.",
    },
    fn: {
      label: "DATA LEAK (Mancato)",
      badgeClass: "status-fn",
      icon: "⚠️",
      description: "Il modello NON ha oscurato questo dato! Rischio violazione privacy.",
    },
    fp: {
      label: "Sovra-oscurato (Falso Positivo)",
      badgeClass: "status-fp",
      icon: "⚡",
      description: "Dato oscurato dal modello ma non catalogato come PII atteso.",
    },
    gold: {
      label: "PII Atteso (Ground Truth)",
      badgeClass: "status-gold",
      icon: "🎯",
      description: "Entità sensibile definita nel benchmark gold standard.",
    },
  },
};
