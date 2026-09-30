/**
 * uiConfig.js
 *
 * Central configuration for the RedactBench UI.
 * Controls auto-refresh intervals, charts, metrics styling, theme defaults,
 * scatter plot metric definitions, and document comparison preferences.
 */

export const uiConfig = {
  // Polling and background synchronization configuration
  polling: {
    defaultIntervalMs: 10000,
    defaultEnabled: true,
    intervalOptions: [
      { label: "Off", value: 0 },
      { label: "5s", value: 5000 },
      { label: "10s", value: 10000 },
      { label: "30s", value: 30000 },
    ],
  },

  // Color tokens aligned with CSS custom properties
  theme: {
    accent: "var(--accent, #4969f5)",
    series2: "var(--series-2, #23a094)",
    risk: "var(--risk, #d25b72)",
  },

  // Distinct palette for plotting multiple models on the same canvas
  modelColors: [
    "#4969f5", // Indigo/Blue
    "#23a094", // Teal
    "#d25b72", // Coral/Red
    "#e67e22", // Orange
    "#8e44ad", // Violet
    "#2980b9", // Cyan/Navy
    "#27ae60", // Green
    "#f39c12", // Gold
    "#16a085", // Sea Green
    "#d35400", // Rust
  ],

  // Chart layout preferences
  charts: {
    scatterHeight: 340,
    barMinHeight: 280,
    barHeightPerItem: 42,
  },

  // Definitions for metrics usable in multi-metric scatter plots
  scatterMetrics: {
    pii_recall: {
      key: "pii_recall",
      label: "PII Recall",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: true,
    },
    latency_p95_ms: {
      key: "latency_p95_ms",
      label: "p95 Latency",
      unit: " ms",
      type: "ms",
      domain: "auto",
      higherIsBetter: false,
    },
    latency_p50_ms: {
      key: "latency_p50_ms",
      label: "p50 Latency",
      unit: " ms",
      type: "ms",
      domain: "auto",
      higherIsBetter: false,
    },
    leakage_rate: {
      key: "leakage_rate",
      label: "Leakage Rate",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: false,
    },
    precision: {
      key: "precision",
      label: "Precision",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: true,
    },
    span_f1: {
      key: "span_f1",
      label: "Span F1",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: true,
    },
    exact_match_recall: {
      key: "exact_match_recall",
      label: "Exact Match Recall",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: true,
    },
    zero_leak_document_rate: {
      key: "zero_leak_document_rate",
      label: "Zero-Leak Docs",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: true,
    },
    over_redaction_rate: {
      key: "over_redaction_rate",
      label: "Over-redaction",
      unit: "%",
      type: "percent",
      domain: [0, 100],
      higherIsBetter: false,
    },
  },

  // Common preconfigured 2D metric comparison presets
  scatterPresets: [
    {
      id: "recall-latency-p95",
      label: "Recall vs p95 Latency",
      x: "latency_p95_ms",
      y: "pii_recall",
    },
    {
      id: "recall-precision",
      label: "Recall vs Precision",
      x: "precision",
      y: "pii_recall",
    },
    {
      id: "recall-leakage",
      label: "Recall vs Leakage",
      x: "leakage_rate",
      y: "pii_recall",
    },
    {
      id: "f1-latency-p50",
      label: "Span F1 vs p50 Latency",
      x: "latency_p50_ms",
      y: "span_f1",
    },
    {
      id: "zeroleak-leakage",
      label: "Zero-Leak vs Leakage",
      x: "leakage_rate",
      y: "zero_leak_document_rate",
    },
  ],

  // Maximum number of failure cases to preview per model
  failureExplorer: {
    maxVisibleCases: 20,
    maxVisibleSpans: 12,
  },

  // Document comparison defaults
  fileComparison: {
    maxVisibleSpans: 8,
  },

  // Executive briefing and decision governance settings
  executive: {
    thresholds: {
      minProductionRecall: 0.85,
      minProductionReliability: 0.95,
      maxAcceptableLeakage: 0.10,
      highZeroLeakDocRate: 0.40,
    },
    riskTiers: {
      low: { label: "Basso Rischio GDPR", tone: "positive" },
      moderate: { label: "Rischio Moderato", tone: "warning" },
      high: { label: "Alto Rischio Sanzioni", tone: "risk" },
    },
    // Return on Investment & TCO comparison with commercial cloud APIs
    roiEstimator: {
      defaultDocsPerMonth: 5000,
      avgTokensPerDoc: 2500,
      cloudCostPerMillionTokens: 4.5, // Reference GPT-4o / Claude blended pricing (€/M tokens)
      localHostingMonthlyEstimate: 160, // Reference GPU instance / amortized on-premise hardware (€/month)
    },
  },
};

export default uiConfig;
