/**
 * textRedactor.js
 *
 * Utilities for slicing canonical document text into interactive segments
 * (plain text chunks and PII redaction spans), handling overlaps safely,
 * applying interactive toggle states, and generating redacted export text.
 */

/**
 * Normalizes and sorts spans to prevent overlapping conflicts.
 * Filters out invalid spans (missing start/end, start >= end, out of text bounds).
 */
export function normalizeSpans(spans, textLength) {
  if (!Array.isArray(spans)) return [];

  const valid = [];
  for (let i = 0; i < spans.length; i++) {
    const s = spans[i];
    const start = Number(s.start);
    const end = Number(s.end);

    if (
      Number.isInteger(start) &&
      Number.isInteger(end) &&
      start >= 0 &&
      end > start &&
      start < textLength
    ) {
      valid.push({
        ...s,
        start,
        end: Math.min(end, textLength),
        id: s.id || `span-${start}-${end}-${s.pii_type || "pii"}-${i}`,
      });
    }
  }

  // Sort primarily by start ASC, then by span length DESC (prefer larger span)
  valid.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.end - a.end;
  });

  // Resolve overlaps cleanly: prevent cursor backward jumps
  const nonOverlapping = [];
  let lastEnd = 0;

  for (const span of valid) {
    if (span.start >= lastEnd) {
      nonOverlapping.push(span);
      lastEnd = span.end;
    } else if (span.end > lastEnd) {
      // Partial overlap: trim start to lastEnd
      nonOverlapping.push({
        ...span,
        start: lastEnd,
      });
      lastEnd = span.end;
    }
    // If span.end <= lastEnd, it is completely contained inside the previous span -> skip
  }

  return nonOverlapping;
}

/**
 * Slices document text into interactive chunks (plain text and PII spans).
 *
 * @param {string} text - Raw canonical document text
 * @param {Array} spans - Array of PII spans
 * @param {Object} options - Configuration options
 * @param {Set<string>} options.toggledSpans - Set of span IDs manually flipped by the user
 * @param {Set<string>} options.disabledTypes - Set of PII types disabled from redaction
 * @param {string} options.viewMode - "redacted" | "revealed" | "audit"
 * @param {string} options.searchQuery - Optional search string
 * @returns {Array<Object>} List of segments ready for rendering
 */
export function buildDocumentSegments(text, spans = [], options = {}) {
  if (typeof text !== "string") {
    return [];
  }

  const {
    toggledSpans = new Set(),
    disabledTypes = new Set(),
    viewMode = "redacted", // "redacted" | "revealed" | "audit"
    searchQuery = "",
  } = options;

  const normalized = normalizeSpans(spans, text.length);
  const segments = [];
  let cursor = 0;

  for (let idx = 0; idx < normalized.length; idx++) {
    const span = normalized[idx];

    // Push preceding plain text chunk if any
    if (span.start > cursor) {
      segments.push({
        type: "text",
        id: `text-${cursor}-${span.start}`,
        content: text.slice(cursor, span.start),
        start: cursor,
        end: span.start,
      });
    }

    // Determine span redaction state:
    // 1. Is this PII type disabled from redaction by category filter?
    const isTypeDisabled = disabledTypes.has(span.pii_type);

    // 2. Base redaction state based on current view mode
    let isRedacted = false;
    if (viewMode === "redacted") {
      // ONLY spans recognized/redacted by the model (or gold baseline) are redacted.
      // False Negatives ('fn') were MISSED by the model: they are DATA LEAKS and must remain in clear text!
      if (span.status === "fn") {
        isRedacted = false;
      } else {
        isRedacted = !isTypeDisabled;
      }
    } else if (viewMode === "revealed") {
      isRedacted = false;
    } else if (viewMode === "audit") {
      // In audit mode, show redacted only if successfully redacted (tp)
      isRedacted = span.status === "tp" && !isTypeDisabled;
    }

    // 3. Check if user individually toggled this specific span
    if (toggledSpans.has(span.id)) {
      isRedacted = !isRedacted;
    }

    const spanContent = text.slice(span.start, span.end);

    segments.push({
      type: "span",
      id: span.id,
      content: spanContent,
      value: span.value || spanContent,
      start: span.start,
      end: span.end,
      pii_type: span.pii_type || "default",
      status: span.status || "redaction", // "tp" | "fn" | "fp" | "gold" | "redaction"
      isRedacted,
      isToggledByUser: toggledSpans.has(span.id),
      modelName: span.modelName || null,
      rawSpan: span,
    });

    cursor = span.end;
  }

  // Push trailing text after last span
  if (cursor < text.length) {
    segments.push({
      type: "text",
      id: `text-${cursor}-${text.length}`,
      content: text.slice(cursor),
      start: cursor,
      end: text.length,
    });
  }

  return segments;
}

/**
 * Formats a PII redaction replacement string based on style.
 */
export function formatRedactionPlaceholder(span, style = "block") {
  const piiLabel = (span.pii_type || "PII").toUpperCase();
  const charLength = Math.max(span.content?.length || 8, 4);

  switch (style) {
    case "pill":
      return `[REDACTED: ${piiLabel}]`;
    case "blur":
      return span.content || "████████";
    case "mask":
      return "*".repeat(charLength);
    case "block":
    default:
      // Solid unicode block matching entity length (min 4, max 24 chars for aesthetics)
      return "█".repeat(Math.min(Math.max(charLength, 6), 20));
  }
}

/**
 * Generates the full document string with active redactions applied.
 * Useful for copying or exporting the redacted text.
 */
export function generateExportText(text, spans = [], options = {}, style = "block") {
  const segments = buildDocumentSegments(text, spans, options);
  let result = "";

  for (const seg of segments) {
    if (seg.type === "text") {
      result += seg.content;
    } else if (seg.isRedacted) {
      result += formatRedactionPlaceholder(seg, style);
    } else {
      result += seg.content;
    }
  }

  return result;
}

/**
 * Extracts distinct PII types with counts from an array of spans.
 */
export function getPiiTypeSummary(spans = []) {
  const counts = new Map();
  for (const s of spans) {
    if (!s.pii_type) continue;
    counts.set(s.pii_type, (counts.get(s.pii_type) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([piiType, count]) => ({ piiType, count }))
    .sort((a, b) => b.count - a.count);
}
